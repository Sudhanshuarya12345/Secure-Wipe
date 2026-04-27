"""Strategy engine — choose_wipe_strategy(), build_execution_plan(), build_execution_preview().

This module determines what operations to run based on device capabilities 
and the selected sanitization depth (STANDARD / ENHANCED / MAXIMUM).
"""

import platform

from utils.constants import (
    MODE_POLICIES,
    EXECUTION_MODE_ALIASES,
    ALL_POLICY_OPERATIONS,
    LINUX_ONLY_POLICY_OPERATIONS,
    WIPE_LEVEL_PROFILES,
    WIPE_LEVEL_ORDER,
    DEVICE_TYPE_HDD,
    DEVICE_TYPE_SATA_SSD,
    DEVICE_TYPE_NVME_SSD,
    WIPE_METHOD_OVERWRITE,
    WIPE_METHOD_SECURE_ERASE,
    WIPE_METHOD_SANITIZE,
    WIPE_METHOD_CRYPTO_ERASE,
    WIPE_METHOD_NVME_FORMAT,
    OP_OVERWRITE,
    OP_SECURE_ERASE,
    OP_NVME_SANITIZE,
    OP_NVME_FORMAT,
    OP_CRYPTO_ERASE,
)

# --- Ordered pipeline steps for the WipePipeline executor ---
PIPELINE_STEPS = [
    'preflight_validation',
    'device_profiling',
    'strategy_selection',
    'hpa_dco_removal',
    'firmware_erase',
    'trim_discard',
    'overwrite_passes',
    'metadata_wipe',
    'verification',
    'reformat',
    'postflight_validation',
]


def normalize_execution_mode(mode_value):
    """Normalize user-visible mode labels/aliases to STANDARD, ENHANCED, or MAXIMUM."""
    if mode_value is None:
        return None
    raw = str(mode_value).strip()
    upper = raw.upper()
    if upper in MODE_POLICIES:
        return upper
    lower = raw.lower()
    return EXECUTION_MODE_ALIASES.get(lower)


def build_execution_plan(mode_value):
    """Build a policy-backed execution plan used by all destructive paths."""
    mode = normalize_execution_mode(mode_value)
    if mode not in MODE_POLICIES:
        raise ValueError("execution mode must be STANDARD, ENHANCED, or MAXIMUM")

    policy = MODE_POLICIES[mode]
    allowed_ops = list(policy['allowed_ops'])
    blocked_ops = sorted(list(ALL_POLICY_OPERATIONS - set(allowed_ops)))

    return {
        'mode': mode,
        'allowed_ops': allowed_ops,
        'blocked_ops': blocked_ops,
        'required_checks': list(policy['required_checks']),
        'metadata_passes': policy.get('metadata_passes', 1),
        'reformat_required': policy.get('reformat_required', True),
        'audit_logging': (mode == 'MAXIMUM'),
        'operations_executed': [],
        'pipeline': list(PIPELINE_STEPS),
    }


def build_execution_preview(mode_value, device_profile=None, capabilities=None):
    """Build a human-readable preview of what a wipe will do — used by the UI before execution."""
    plan = build_execution_plan(mode_value)
    strategy = choose_wipe_strategy(device_profile or {}, plan, capabilities or {})

    mode = plan['mode']
    profile = WIPE_LEVEL_PROFILES.get(mode.lower(), {})

    preview = {
        'mode': mode,
        'label': profile.get('label', mode),
        'description': profile.get('description', ''),
        'technical_note': profile.get('technical_note', ''),
        'wipe_method': strategy.get('wipe_method', WIPE_METHOD_OVERWRITE),
        'firmware_operation': strategy.get('firmware_operation', False),
        'hidden_area_handling': strategy.get('hidden_area_handling', 'Not covered'),
        'metadata_passes': plan.get('metadata_passes', 1),
        'reformat_required': True,
        'warnings': list(strategy.get('warnings', [])),
        'pipeline': plan.get('pipeline', []),
    }
    return preview


def normalize_execution_plan(execution_plan):
    """Validate and normalize execution plan input."""
    if isinstance(execution_plan, str):
        return build_execution_plan(execution_plan)
    if isinstance(execution_plan, dict):
        mode = normalize_execution_mode(execution_plan.get('mode'))
        if not mode:
            raise ValueError("execution plan is missing a valid mode")
        rebuilt = build_execution_plan(mode)
        if isinstance(execution_plan.get('operations_executed'), list):
            rebuilt['operations_executed'] = execution_plan.get('operations_executed')
        return rebuilt
    raise ValueError("execution plan is required for destructive operations")


def is_operation_allowed(execution_plan, operation_name):
    """Return True when the operation is permitted by policy."""
    plan = normalize_execution_plan(execution_plan)
    return operation_name in set(plan.get('allowed_ops', []))


def enforce_operation_allowed(execution_plan, operation_name):
    """Hard-block any operation not allowed by the active execution plan."""
    plan = normalize_execution_plan(execution_plan)
    if operation_name not in set(plan.get('allowed_ops', [])):
        raise PermissionError(
            f"Operation '{operation_name}' is blocked in mode {plan.get('mode')}"
        )


def get_linux_only_requested_operations(execution_plan):
    """Return Linux-only operations requested by the active execution plan."""
    plan = normalize_execution_plan(execution_plan)
    requested = set(plan.get('allowed_ops', [])) & LINUX_ONLY_POLICY_OPERATIONS
    return sorted(requested)


def enforce_linux_platform_for_execution_plan(
    execution_plan,
    operation_kind='format',
    error_cls=RuntimeError,
):
    """Require Linux when the selected plan needs Linux-only low-level controls."""
    if str(operation_kind or '').lower() != 'format':
        return
    if platform.system() == 'Linux':
        return

    plan = normalize_execution_plan(execution_plan)
    requested = get_linux_only_requested_operations(plan)
    if not requested:
        return

    ops = ', '.join(requested)
    raise error_cls(
        f"Mode {plan.get('mode')} requires Linux for low-level operations ({ops}). "
        "Use STANDARD mode on this platform or run this operation on Linux."
    )


def _get_passes(device_type, level):
    """Return recommended overwrite pass count per device + level."""
    if device_type in (DEVICE_TYPE_SATA_SSD, DEVICE_TYPE_NVME_SSD):
        return 1  # Multi-pass is pointless for SSD (FTL remaps writes)
    if level == 'MAXIMUM':
        return 3
    return 3  # Default for HDD


def _get_pattern(device_type, level):
    """Return recommended overwrite pattern."""
    return 'all'  # random -> zeroes -> ones cycling


def _select_firmware_op(device_type, capabilities):
    """Select the best firmware erase operation for the device."""
    if device_type == DEVICE_TYPE_NVME_SSD:
        if capabilities.get('supports_nvme_sanitize'):
            return OP_NVME_SANITIZE
        if capabilities.get('supports_nvme_format'):
            return OP_NVME_FORMAT
    if device_type in (DEVICE_TYPE_HDD, DEVICE_TYPE_SATA_SSD):
        if capabilities.get('supports_secure_erase'):
            return OP_SECURE_ERASE
    return None


def choose_wipe_strategy(device_profile, execution_plan, capabilities):
    """Choose wipe method per device class and supported firmware capabilities."""
    plan = normalize_execution_plan(execution_plan)
    device_profile = device_profile or {}
    capabilities = capabilities or {}

    mode = plan.get('mode')
    device_type = device_profile.get('device_type', DEVICE_TYPE_SATA_SSD)

    strategy = {
        'device_type': device_type,
        'wipe_method': WIPE_METHOD_OVERWRITE,
        'operation_name': OP_OVERWRITE,
        'sanitize_action': None,
        'use_enhanced_secure_erase': False,
        'firmware_operation': False,
        'firmware_op': None,
        'hidden_area_handling': 'Not covered',
        'remapped_sector_handling': 'not_covered',
        'overprovisioned_block_handling': 'not_covered',
        'irrecoverability_level': 'Basic',
        'irrecoverability_claim': 'Data overwritten (may not affect hidden/internal blocks)',
        'overwrite_passes': _get_passes(device_type, mode),
        'overwrite_pattern': _get_pattern(device_type, mode),
        'metadata_wipe': True,
        'metadata_passes': plan.get('metadata_passes', 1),
        'hpa_dco_removal': (mode == 'MAXIMUM'),
        'crypto_erase': False,
        'trim_discard': device_type in (DEVICE_TYPE_SATA_SSD, DEVICE_TYPE_NVME_SSD),
        'verify_after': True,
        'reformat': True,
        'warnings': [],
    }

    supports_secure = bool(capabilities.get('supports_secure_erase'))
    supports_enhanced = bool(capabilities.get('supports_enhanced_erase'))
    supports_nvme_sanitize = bool(capabilities.get('supports_nvme_sanitize'))
    supports_nvme_format = bool(capabilities.get('supports_nvme_format'))
    supports_crypto = bool(capabilities.get('supports_crypto_erase'))
    frozen_state = bool(capabilities.get('frozen_state'))

    # Select firmware operation if level allows it
    if mode in ('ENHANCED', 'MAXIMUM'):
        strategy['firmware_op'] = _select_firmware_op(device_type, capabilities)

    if mode == 'MAXIMUM':
        strategy['crypto_erase'] = supports_crypto

    if device_type == DEVICE_TYPE_HDD:
        if frozen_state:
            strategy['warnings'].append('Drive reports frozen security state; secure erase is skipped')
        elif is_operation_allowed(plan, OP_SECURE_ERASE) and supports_secure:
            strategy.update({
                'wipe_method': WIPE_METHOD_SECURE_ERASE,
                'operation_name': OP_SECURE_ERASE,
                'use_enhanced_secure_erase': supports_enhanced,
                'firmware_operation': True,
                'hidden_area_handling': 'Indirect',
                'remapped_sector_handling': 'indirect',
                'overprovisioned_block_handling': 'indirect',
                'irrecoverability_level': 'Strong',
                'irrecoverability_claim': 'Firmware-level erase performed (includes most hidden areas)',
            })
        else:
            strategy['warnings'].append('ATA secure erase unavailable or blocked; using overwrite fallback')

    elif device_type == DEVICE_TYPE_SATA_SSD:
        if frozen_state:
            strategy['warnings'].append('Drive reports frozen security state; secure erase is skipped')
        elif is_operation_allowed(plan, OP_SECURE_ERASE) and supports_secure:
            strategy.update({
                'wipe_method': WIPE_METHOD_SECURE_ERASE,
                'operation_name': OP_SECURE_ERASE,
                'use_enhanced_secure_erase': supports_enhanced,
                'firmware_operation': True,
                'hidden_area_handling': 'Indirect',
                'remapped_sector_handling': 'indirect',
                'overprovisioned_block_handling': 'indirect',
                'irrecoverability_level': 'Strong',
                'irrecoverability_claim': 'Firmware-level erase performed (includes most hidden areas)',
            })
        else:
            strategy['warnings'].append('SSD overwrite fallback selected; wear-leveled blocks may not be fully affected')

    elif device_type == DEVICE_TYPE_NVME_SSD:
        if is_operation_allowed(plan, OP_NVME_SANITIZE) and supports_nvme_sanitize:
            sanitize_action = 'block'
            wipe_method = WIPE_METHOD_SANITIZE
            claim = 'Controller-level sanitize performed (affects internal NAND)'
            level = 'Strong'
            op_name = OP_NVME_SANITIZE

            if supports_crypto and mode in ('ENHANCED', 'MAXIMUM'):
                sanitize_action = 'crypto'
                wipe_method = WIPE_METHOD_CRYPTO_ERASE
                claim = 'All data cryptographically unrecoverable'
                level = 'Maximum (practical)'
                op_name = OP_NVME_SANITIZE
            elif mode == 'MAXIMUM':
                sanitize_action = 'overwrite'

            strategy.update({
                'wipe_method': wipe_method,
                'operation_name': op_name,
                'sanitize_action': sanitize_action,
                'firmware_operation': True,
                'hidden_area_handling': 'Indirect',
                'remapped_sector_handling': 'indirect',
                'overprovisioned_block_handling': 'indirect',
                'irrecoverability_level': level,
                'irrecoverability_claim': claim,
            })
        elif is_operation_allowed(plan, OP_NVME_FORMAT) and supports_nvme_format:
            strategy.update({
                'wipe_method': WIPE_METHOD_NVME_FORMAT,
                'operation_name': OP_NVME_FORMAT,
                'firmware_operation': True,
                'hidden_area_handling': 'Indirect',
                'remapped_sector_handling': 'indirect',
                'overprovisioned_block_handling': 'indirect',
                'irrecoverability_level': 'Basic',
                'irrecoverability_claim': 'Data overwritten (may not affect hidden/internal blocks)',
            })
            strategy['warnings'].append('NVMe sanitize unsupported; using NVMe format fallback (less thorough)')
        else:
            strategy['warnings'].append('NVMe sanitize unavailable or blocked; using overwrite fallback')

    for note in capabilities.get('notes', []):
        if note and note not in strategy['warnings']:
            strategy['warnings'].append(note)

    if strategy.get('firmware_operation'):
        power_note = capabilities.get('power_stability_warning')
        if power_note and power_note not in strategy['warnings']:
            strategy['warnings'].append(power_note)

    return strategy
