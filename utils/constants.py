import os
from colorama import Fore, Style

# Terminal colors
GREEN  = Fore.GREEN
YELLOW = Fore.YELLOW
BLUE   = Fore.BLUE
MAGENTA = Fore.MAGENTA
CYAN   = Fore.CYAN
RESET  = Style.RESET_ALL
BRIGHT = Style.BRIGHT

# Claim levels used across CLI/UI/certificate flows.
CLAIM_STANDARD = "DATA_OVERWRITTEN"
CLAIM_ENHANCED = "MAXIMUM_PRACTICAL_UNRECOVERABILITY"
CLAIM_MAXIMUM  = "COMPREHENSIVE_SANITIZATION"
CLAIM_LIMITED  = "INCOMPLETE_OR_UNVERIFIED"

# Backward compatibility alias
CLAIM_MAX_PRACTICAL = CLAIM_ENHANCED

CLAIM_STATEMENTS = {
    CLAIM_STANDARD: "All addressable data and filesystem metadata have been overwritten. "
                    "Standard forensic recovery tools will not recover file content.",
    CLAIM_ENHANCED: "Maximum practical unrecoverability achieved. Firmware-assisted erase "
                    "used where supported. Over-provisioned/wear-leveled areas addressed "
                    "to extent possible.",
    CLAIM_MAXIMUM:  "Comprehensive sanitization completed including hidden regions (HPA/DCO), "
                    "firmware-level erase, crypto erase, and multi-pass metadata destruction.",
    CLAIM_LIMITED:  "Wipe completed with warnings. One or more steps failed or were skipped. "
                    "Review audit log for details.",
}

VALID_PATTERNS = {'all', 'zeroes', 'ones', 'random'}
MIN_WIPE_BLOCK_SIZE = 512 * 1024
MAX_WIPE_BLOCK_SIZE = 8 * 1024 * 1024
DEFAULT_WIPE_BLOCK_SIZE = MAX_WIPE_BLOCK_SIZE
VERIFY_INTERVAL_BYTES = 64 * 1024 * 1024

# New canonical wipe levels
WIPE_LEVEL_ORDER = ('standard', 'enhanced', 'maximum')

# Backward compatibility aliases
WIPE_LEVEL_ALIASES = {
    'standard': 'standard', 'enhanced': 'enhanced', 'maximum': 'maximum',
    'safe': 'standard', 'controlled': 'enhanced', 'risky': 'maximum',
    'advanced': 'enhanced', 'expert': 'maximum',
    'easy': 'standard', 'low': 'standard', 'medium': 'enhanced', 'high': 'maximum',
    '1': 'standard', '2': 'enhanced', '3': 'maximum',
}

EXECUTION_MODE_ALIASES = {
    'standard': 'STANDARD', 'enhanced': 'ENHANCED', 'maximum': 'MAXIMUM',
    'safe': 'STANDARD', 'controlled': 'ENHANCED', 'advanced': 'ENHANCED',
    'risky': 'MAXIMUM', 'expert': 'MAXIMUM',
}

WIPE_LEVEL_PROFILES = {
    'standard': {
        'label': 'Standard Wipe',
        'mode': 'STANDARD',
        'depth': 'BASE',
        'description': 'Overwrites all data and filesystem metadata. Suitable for resale or reuse.',
        'technical_note': 'Multi-pass overwrite of addressable LBAs + filesystem metadata destruction + reformat.',
    },
    'enhanced': {
        'label': 'Enhanced Wipe',
        'mode': 'ENHANCED',
        'depth': 'FIRMWARE',
        'description': 'Adds hardware-level secure erase when supported. Recommended for SSDs.',
        'technical_note': 'Firmware-assisted erase (ATA SE / NVMe Sanitize) when available, with full software fallback.',
    },
    'maximum': {
        'label': 'Maximum Wipe',
        'mode': 'MAXIMUM',
        'depth': 'FULL',
        'description': 'Targets hidden and reserved areas (HPA/DCO) and uses all available methods.',
        'technical_note': 'HPA/DCO removal + crypto erase + additional metadata passes + firmware sanitize + overwrite.',
    },
}

OP_OVERWRITE = 'overwrite'
OP_FORMAT = 'format'
OP_PARTITION_RESET = 'partition_reset'
OP_HPA_MODIFY = 'HPA_modify'
OP_HPA_EXPAND = 'HPA_expand'
OP_DCO_MODIFY = 'DCO_modify'
OP_SECURE_ERASE = 'secure_erase'
OP_NVME_SANITIZE = 'nvme_sanitize'
OP_CRYPTO_ERASE = 'crypto_erase'
OP_NVME_FORMAT = 'nvme_format'
OP_RAW_COMMANDS = 'raw_commands'

DEVICE_TYPE_HDD = 'HDD'
DEVICE_TYPE_SATA_SSD = 'SATA_SSD'
DEVICE_TYPE_NVME_SSD = 'NVME_SSD'

WIPE_METHOD_OVERWRITE = 'Overwrite'
WIPE_METHOD_SECURE_ERASE = 'Secure Erase'
WIPE_METHOD_SANITIZE = 'Sanitize'
WIPE_METHOD_CRYPTO_ERASE = 'Crypto Erase'
WIPE_METHOD_NVME_FORMAT = 'NVMe Format'

ALL_POLICY_OPERATIONS = {
    OP_OVERWRITE,
    OP_FORMAT,
    OP_PARTITION_RESET,
    OP_HPA_MODIFY,
    OP_HPA_EXPAND,
    OP_DCO_MODIFY,
    OP_SECURE_ERASE,
    OP_NVME_SANITIZE,
    OP_CRYPTO_ERASE,
    OP_NVME_FORMAT,
    OP_RAW_COMMANDS,
}

LINUX_ONLY_POLICY_OPERATIONS = {
    OP_HPA_EXPAND,
    OP_DCO_MODIFY,
    OP_SECURE_ERASE,
    OP_NVME_SANITIZE,
    OP_CRYPTO_ERASE,
    OP_NVME_FORMAT,
}

MODE_POLICIES = {
    'STANDARD': {
        'allowed_ops': [OP_OVERWRITE, OP_FORMAT, OP_PARTITION_RESET],
        'required_checks': ['system_disk_protection', 'mount_in_use_check',
                           'disk_identity_verification', 'hpa_dco_baseline'],
        'metadata_passes': 1,
        'reformat_required': True,
    },
    'ENHANCED': {
        'allowed_ops': [OP_OVERWRITE, OP_FORMAT, OP_PARTITION_RESET,
                       OP_SECURE_ERASE, OP_NVME_SANITIZE, OP_NVME_FORMAT],
        'required_checks': ['system_disk_protection', 'mount_in_use_check',
                           'disk_identity_verification', 'hpa_dco_baseline',
                           'device_capability_detection', 'secure_erase_interrupt_lock',
                           'power_stability_warning'],
        'metadata_passes': 1,
        'reformat_required': True,
    },
    'MAXIMUM': {
        'allowed_ops': sorted(ALL_POLICY_OPERATIONS),
        'required_checks': ['system_disk_protection', 'mount_in_use_check',
                           'disk_identity_verification', 'hpa_dco_baseline',
                           'device_capability_detection', 'power_stability_warning',
                           'expert_audit_logging'],
        'metadata_passes': 2,
        'reformat_required': True,
    },
}

REQUIRED_CHECK_SEVERITY = {
    'system_disk_protection': 'block',
    'mount_in_use_check': 'block',
    'disk_identity_verification': 'block',
    'hpa_dco_baseline': 'block',
    'device_capability_detection': 'warning',
    'secure_erase_interrupt_lock': 'record',
    'power_stability_warning': 'warning',
    'expert_audit_logging': 'record',
}

# Legacy destroy workflow constants (retained for backward compat with securewipeUI imports)
DESTROY_METHODS = {'shredding', 'degaussing', 'incineration', 'crushing', 'drilling', 'other'}
DESTROY_ACK_PHRASE = "I CONFIRM PHYSICAL DESTRUCTION COMPLETED"

# The parent directory of the 'utils' directory
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WIPE_AUDIT_DIR = os.path.join(_BASE_DIR, 'wipe_audit')
DESTROY_RECORD_DIR = os.path.join(_BASE_DIR, 'destroy_records')
