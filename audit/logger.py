import os
import json
import uuid
import datetime

from utils.constants import WIPE_AUDIT_DIR, WIPE_METHOD_OVERWRITE

def create_execution_report(
    execution_plan,
    target_disk,
    operation_kind='format',
    device_profile=None,
    wipe_strategy=None,
    preflight_details=None,
):
    """Initialize a structured audit report for execution."""
    plan = execution_plan or {}
    device_profile = device_profile or {}
    wipe_strategy = wipe_strategy or {}
    preflight = preflight_details or {}

    hidden_status = preflight.get('hidden_status', {})
    hpa_present = bool(hidden_status.get('hpa_present'))
    dco_restricted = bool(hidden_status.get('dco_restricted'))

    return {
        'mode': plan.get('mode', 'STANDARD'),
        'operations_executed': [],
        'depth': plan.get('mode', 'STANDARD'),
        'device_type': device_profile.get('device_type', 'unknown'),
        'device_transport': device_profile.get('transport', 'unknown'),
        'device_model': device_profile.get('model', 'Unknown'),
        'wipe_method': wipe_strategy.get('wipe_method', WIPE_METHOD_OVERWRITE),
        'hpa_status': 'present' if hpa_present else 'not_detected',
        'dco_status': 'restricted' if dco_restricted else 'not_restricted',
        'remapped_sector_handling': wipe_strategy.get('remapped_sector_handling', 'not_covered'),
        'overprovisioned_block_handling': wipe_strategy.get('overprovisioned_block_handling', 'not_covered'),
        'irrecoverability_level': wipe_strategy.get('irrecoverability_level', 'Basic'),
        'irrecoverability_claim': wipe_strategy.get('irrecoverability_claim', 'Data overwritten (may not affect hidden/internal blocks)'),
        'reusability_status': 'UNKNOWN',
        'hpa_detected': hpa_present,
        'hpa_removed': False,
        'dco_modified': False,
        'final_sector_check': 'FAIL',
        'reusability_test': 'FAIL',
        'final_status': 'UNSAFE',
        'warnings': list(wipe_strategy.get('warnings') or []),
        'target_disk': target_disk,
        'operation_kind': operation_kind,
        'created_utc': datetime.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
    }

def add_report_step(report, operation_name, status, before=None, after=None, details=None):
    """Append operation step state to audit report."""
    step = {
        'operation_name': operation_name,
        'status': status,
        'before': before,
        'after': after,
        'details': details,
    }
    report.setdefault('operations_executed', []).append(step)

def save_execution_report(report, output_dir=WIPE_AUDIT_DIR):
    """Persist structured audit report and return file path."""
    os.makedirs(output_dir, exist_ok=True)
    report_id = str(uuid.uuid4())
    report_path = os.path.join(output_dir, f"wipe_report_{report_id}.json")
    payload = dict(report)
    payload['report_id'] = report_id
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, indent=2, sort_keys=True)
    return report_path
