from utils.constants import (
    CLAIM_STANDARD, CLAIM_ENHANCED, CLAIM_MAXIMUM, CLAIM_LIMITED,
    CLAIM_STATEMENTS
)

def determine_claim_level(level, device_type, firmware_used, verification_passed, hpa_cleared):
    """Determine the final claim level based on operations performed and verification."""
    if not verification_passed:
        return CLAIM_LIMITED

    if level == 'MAXIMUM':
        if device_type == 'HDD' and not hpa_cleared:
            return CLAIM_ENHANCED  # Downgrade: hidden areas may persist
        return CLAIM_MAXIMUM

    if level == 'ENHANCED':
        return CLAIM_ENHANCED

    return CLAIM_STANDARD

def build_claim_result(
    operation,
    claim_level,
    verification_requested=False,
    verification_passed=False,
    hardware_sanitize_used=False,
    notes=None,
    execution_report=None,
    report_path=None
):
    """Build a structured claim statement for reporting and certificate generation."""
    notes = notes or []
    
    statement = CLAIM_STATEMENTS.get(
        claim_level, 
        "Sanitization is incomplete or unverified."
    )

    return {
        'operation': operation,
        'claim_level': claim_level,
        'claim_statement': statement,
        'verification_requested': verification_requested,
        'verification_passed': verification_passed,
        'hardware_sanitize_used': hardware_sanitize_used,
        'safety_verdict': "REUSABLE" if verification_passed else "UNKNOWN",
        'notes': notes,
        'execution_report': execution_report,
        'report_path': report_path
    }
