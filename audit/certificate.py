"""Certificate generation and destroy workflow records.

NOTE: The physical destruction workflow has been removed from the active UI.
These functions are retained for backward compatibility with existing audit 
records and the legacy securewipeUI.py imports.
"""

import os
import json
import uuid
import datetime
import hashlib

from utils.constants import DESTROY_RECORD_DIR, DESTROY_METHODS, DESTROY_ACK_PHRASE
from utils.formatting import format_size, format_time_human_readable

def generate_sanitization_certificate(report_data, output_path):
    """Generate a human-readable text certificate from a wipe report."""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    cert = []
    cert.append("================================================================================")
    cert.append("                      SECURE-WIPE SANITIZATION CERTIFICATE                      ")
    cert.append("================================================================================")
    cert.append("")
    cert.append(f" Certificate ID:  {report_data.get('report_id', 'N/A')}")
    cert.append(f" Generated Date:  {now}")
    cert.append(f" Status:          {report_data.get('final_status', 'SUCCESS')}")
    cert.append("")
    cert.append("--------------------------------------------------------------------------------")
    cert.append(" DEVICE INFORMATION")
    cert.append("--------------------------------------------------------------------------------")
    cert.append(f" Target Device:   {report_data.get('target_disk', 'Unknown')}")
    cert.append(f" Device Model:    {report_data.get('device_model', 'Unknown')}")
    cert.append(f" Device Type:     {report_data.get('device_type', 'Unknown')}")
    cert.append(f" Serial Number:   {report_data.get('device_serial', 'N/A')}")
    cert.append("")
    cert.append("--------------------------------------------------------------------------------")
    cert.append(" OPERATION SUMMARY")
    cert.append("--------------------------------------------------------------------------------")
    cert.append(f" Wipe Mode:       {report_data.get('mode', 'STANDARD')}")
    cert.append(f" Claim Level:     {report_data.get('irrecoverability_level', 'Basic')}")
    cert.append(f" Claim Statement: {report_data.get('irrecoverability_claim', 'N/A')}")
    
    start_time = report_data.get('start_time', 0)
    end_time = report_data.get('end_time', 0)
    if start_time and end_time:
        duration = end_time - start_time
        cert.append(f" Total Duration:  {format_time_human_readable(duration)}")
    
    cert.append("")
    cert.append("--------------------------------------------------------------------------------")
    cert.append(" AUDIT LOG (SUMMARY)")
    cert.append("--------------------------------------------------------------------------------")
    
    for step in report_data.get('operations_executed', []):
        name = step.get('operation_name', 'Unknown')
        status = step.get('status', 'Unknown')
        cert.append(f" [ {status.upper():7} ] {name}")
        
    cert.append("")
    cert.append("--------------------------------------------------------------------------------")
    cert.append(" VERIFICATION & REUSABILITY")
    cert.append("--------------------------------------------------------------------------------")
    cert.append(f" Verification:    {report_data.get('final_sector_check', 'FAIL')}")
    cert.append(f" Reusability:     {report_data.get('reusability_status', 'UNKNOWN')}")
    cert.append("")
    cert.append("================================================================================")
    cert.append(" END OF CERTIFICATE")
    cert.append("================================================================================")

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(cert))
    
    return output_path
    """Hash a file using SHA-256 for evidence integrity tracking."""
    digest = hashlib.sha256()
    with open(file_path, 'rb') as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def normalize_destroy_method(method):
    """Normalize destruction method to a known set for audit consistency."""
    normalized = (method or 'other').lower().strip()
    if normalized not in DESTROY_METHODS:
        return 'other'
    return normalized


def build_destroy_workflow_record(
    device_id,
    operator_name,
    destruction_method,
    acknowledgement_text,
    evidence_paths,
    location=None,
    witness_name=None,
    notes=None,
    operation_reference=None,
):
    """Build an auditable destroy workflow record with evidence metadata."""
    if not device_id:
        raise ValueError("device_id is required for destroy workflow")
    if not operator_name:
        raise ValueError("operator_name is required for destroy workflow")
    if acknowledgement_text != DESTROY_ACK_PHRASE:
        raise ValueError("operator acknowledgement phrase does not match required text")
    if not evidence_paths or len(evidence_paths) < 2:
        raise ValueError("at least 2 evidence files are required for destroy workflow")
    if not witness_name:
        raise ValueError("witness name is required for destroy workflow")

    method = normalize_destroy_method(destruction_method)
    evidence = []

    for path in evidence_paths:
        abs_path = os.path.abspath(path)
        exists = os.path.exists(abs_path)
        evidence_entry = {
            'path': abs_path,
            'exists': exists,
        }
        if exists and os.path.isfile(abs_path):
            evidence_entry['size_bytes'] = os.path.getsize(abs_path)
            evidence_entry['sha256'] = hash_file_sha256(abs_path)
        evidence.append(evidence_entry)

    existing_evidence = [item for item in evidence if item.get('exists')]
    if len(existing_evidence) < 2:
        raise ValueError("minimum 2 existing evidence files required")

    record = {
        'record_id': str(uuid.uuid4()),
        'created_utc': datetime.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
        'device_id': str(device_id),
        'operator_name': operator_name,
        'destruction_method': method,
        'acknowledgement_text': acknowledgement_text,
        'required_acknowledgement_text': DESTROY_ACK_PHRASE,
        'location': location,
        'witness_name': witness_name,
        'notes': notes,
        'operation_reference': operation_reference,
        'evidence': evidence,
        'evidence_count': len(existing_evidence),
        'witness_signature_file': existing_evidence[0]['path'] if existing_evidence else None,
        'server_verification_status': 'pending',
    }

    record['record_fingerprint'] = hashlib.sha256(
        json.dumps(record, sort_keys=True).encode('utf-8')
    ).hexdigest()
    return record


def save_destroy_workflow_record(record, output_dir=DESTROY_RECORD_DIR):
    """Persist a destroy workflow record as JSON and return the file path."""
    os.makedirs(output_dir, exist_ok=True)
    record_id = record.get('record_id', str(uuid.uuid4()))
    record_path = os.path.join(output_dir, f"destroy_record_{record_id}.json")
    with open(record_path, 'w', encoding='utf-8') as f:
        json.dump(record, f, indent=2, sort_keys=True)
    return record_path


def load_destroy_workflow_record(record_path):
    """Load a destroy workflow record JSON file."""
    with open(record_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def validate_destroy_workflow_record(record):
    """Validate destroy workflow integrity and required evidence/ack fields."""
    reasons = []

    if not isinstance(record, dict):
        return False, ["record format is invalid"]

    required_fields = ['record_id', 'device_id', 'operator_name', 'destruction_method', 'evidence', 'witness_name']
    for field_name in required_fields:
        if not record.get(field_name):
            reasons.append(f"missing required field: {field_name}")

    if record.get('acknowledgement_text') != DESTROY_ACK_PHRASE:
        reasons.append("acknowledgement text does not match required phrase")

    evidence = record.get('evidence', [])
    if not evidence or len(evidence) < 2:
        reasons.append("minimum 2 evidence files required")
    else:
        existing = [item for item in evidence if item.get('exists')]
        if len(existing) < 2:
            reasons.append("minimum 2 existing evidence files required")

    if not record.get('witness_signature_file'):
        reasons.append("witness signature file missing")

    record_fingerprint = record.get('record_fingerprint')
    if record_fingerprint:
        check_record = dict(record)
        check_record.pop('record_fingerprint', None)
        expected_fingerprint = hashlib.sha256(
            json.dumps(check_record, sort_keys=True).encode('utf-8')
        ).hexdigest()
        if record_fingerprint != expected_fingerprint:
            reasons.append("record fingerprint validation failed")

    return len(reasons) == 0, reasons


def verify_destroy_record_server(record):
    """Stub for server-side destroy-record verification. Returns status."""
    return 'verified' if record.get('record_id') else 'unverified'
