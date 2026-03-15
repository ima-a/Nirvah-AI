import hashlib
import json
from datetime import datetime, timezone
from constants import HASH_PREFIX, GENESIS_HASH

def compute_hash(data_dict: dict) -> str:
    """
    Law #7: Hash the plaintext.
    Sorts keys to ensure canonical JSON representation.
    """
    # Create a copy and remove the 'hash' field if it exists
    data_to_hash = data_dict.copy()
    data_to_hash.pop("hash", None)
    
    # Canonical JSON string [cite: 322]
    encoded_data = json.dumps(data_to_hash, sort_keys=True).encode()
    return f"{HASH_PREFIX}{hashlib.sha256(encoded_data).hexdigest()}"

def create_audit_entry(record_id: str, payload: dict, prev_hash: str = GENESIS_HASH):
    """
    Creates a LOG-03 Audit Chain entry. [cite: 312]
    """
    # 1. Compute hash of the plaintext payload
    payload_hash = compute_hash(payload)
    
    # 2. Construct the Audit Log entry [cite: 315]
    audit_entry = {
        "log_type": "AUDIT_CHAIN",
        "id": record_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload_hash": payload_hash,
        "previous_hash": prev_hash,
        "hash": None # Placeholder
    }
    
    # 3. Compute final hash over the whole entry
    audit_entry["hash"] = compute_hash(audit_entry)
    
    return audit_entry

# --- Quick Test ---
if __name__ == "__main__":
    # Mock health record (Plaintext)
    mock_payload = {"bp_systolic": 120, "bp_diastolic": 80, "weight": 65}
    
    # Create Block 1 (Chained to Genesis)
    block1 = create_audit_entry("NV-001", mock_payload, GENESIS_HASH)
    print(f"Block 1 Hash: {block1['hash']}")
    
    # Create Block 2 (Chained to Block 1)
    block2 = create_audit_entry("NV-002", mock_payload, block1['hash'])
    print(f"Block 2 Hash: {block2['hash']}")
    print(f"Block 2 Previous Hash Match: {block2['previous_hash'] == block1['hash']}")
