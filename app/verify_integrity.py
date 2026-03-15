import json
import hashlib
from app.constants import GENESIS_HASH
from app.audit_chain import compute_hash

def verify_full_chain(db_records: list):
    """
    Law #6: Verify the append-only ledger integrity.
   
    """
    print(f"--- Integrity Scan Started: {len(db_records)} blocks found ---")
    
    expected_prev_hash = GENESIS_HASH
    errors = []

    for record in db_records:
        record_id = record.get('id')
        current_hash = record.get('hash')
        provided_prev_hash = record.get('previous_hash')

        # 1. Check Chain Continuity [cite: 355, 356]
        if provided_prev_hash != expected_prev_hash:
            errors.append(f"[TAMPER ALERT] Chain broken at {record_id}: Previous hash mismatch!")

        # 2. Re-compute Hash to detect Row-Level changes [cite: 352, 353]
        recomputed_hash = compute_hash(record)
        if current_hash != recomputed_hash:
            errors.append(f"[DATA CORRUPTION] Row content tampered at {record_id}!")

        # Move to next link
        expected_prev_hash = current_hash

    if not errors:
        print("[SUCCESS] Audit Chain Integrity Verified. No tampering detected.")
        return True
    else:
        for err in errors:
            print(err)
        return False

# --- Simulation Test ---
if __name__ == "__main__":
    # Mock data from Supabase
    block1 = {"id": "NV-001", "payload_hash": "h1", "previous_hash": GENESIS_HASH}
    block1["hash"] = compute_hash(block1)
    
    block2 = {"id": "NV-002", "payload_hash": "h2", "previous_hash": block1["hash"]}
    block2["hash"] = compute_hash(block2)
    
    # Test 1: Valid Chain
    verify_full_chain([block1, block2])
    
    # Test 2: Simulate Tampering (Changing a value in Block 1)
    print("\n--- Simulating Tampering in Block 1 ---")
    block1["payload_hash"] = "TAMPERED_DATA"
    verify_full_chain([block1, block2])
