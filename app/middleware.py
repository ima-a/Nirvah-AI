from app import constants
from app.pii_utils import strip_pii, hash_identifier
from datetime import datetime, timezone

def process_webhook_entry(raw_body: str, sender_phone: str):
    """
    Law #1 & #2: PII stripping and hashing at the entry point.
   
    """
    # 1. Strip raw PII from text before it enters the pipeline [cite: 849]
    clean_text = strip_pii(raw_body)
    
    # 2. Hash the sender phone - original never stored
    sender_hash = hash_identifier(sender_phone)
    
    # 3. Create LOG-01 Webhook Raw object (Memory Only)
    webhook_log = {
        "log_type": constants.WEBHOOK_RAW,
        "sender_hash": sender_hash,
        "body_text": clean_text,
        "pii_detected": "[REDACTED]" in clean_text,
        "timestamp_received": datetime.now(timezone.utc).isoformat()
    }
    
    return webhook_log

def create_access_log(user_id: str, role: str, action: str, resource_id: str):
    """
    Law #5: Mandatory DPDP Act 2023 compliance trail.
   
    """
    access_event = {
        "log_type": constants.ACCESS_EVENT,
        "user_id_hash": hash_identifier(user_id),
        "user_role": role, # ASHA | SUPERVISOR | DISTRICT_OFFICER
        "action": action,   # READ | WRITE | EXPORT
        "resource_id": resource_id,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    return access_event

def handle_consent_logic(command: str):
    """
    DPDP Compliance: Handle STOP and RECORD commands.
    [cite: 880, 881, 884, 888]
    """
    cmd = command.strip().upper()
    if cmd == "STOP":
        return "CONSENT_WITHDRAWN" # Updates citizen_tracker_opted_out
    elif cmd == "RECORD":
        return "DATA_ACCESS_REQUEST" # Triggers full health history send
    return "STANDARD_VISIT"

# --- Final Integration Test ---
if __name__ == "__main__":
    # Test Entry Point (LOG-01)
    raw_in = "Sunita (Aadhaar: 212345678901) visit done."
    phone = "+919876543210"
    processed = process_webhook_entry(raw_in, phone)
    
    print("--- LOG-01 Webhook Entry ---")
    print(f"Hashed Sender: {processed['sender_hash']}")
    print(f"Clean Body: {processed['body_text']}")
    
    # Test Compliance Logging (LOG-05)
    access = create_access_log("supervisor_01", "SUPERVISOR", "READ", "NV-2847")
    print("\n--- LOG-05 Access Event ---")
    print(f"User Hash: {access['user_id_hash']}")
    print(f"Action: {access['action']} on {access['resource_id']}")
