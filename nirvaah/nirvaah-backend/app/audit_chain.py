import hashlib
import json
from datetime import datetime, timezone


def generate_hash(data_block):
	"""Create a deterministic SHA-256 hash of a dictionary."""
	block_string = json.dumps(data_block, sort_keys=True).encode()
	return hashlib.sha256(block_string).hexdigest()


def create_audit_entry(record, worker_id, previous_hash="0" * 64):
	"""Create a chained audit entry for the ledger."""
	entry_data = {
		"record_id": record.get("id"),
		"worker_id": worker_id,
		"timestamp": datetime.now(timezone.utc).isoformat(),
		"previous_hash": previous_hash,
		"record_snapshot": record,
	}
	entry_data["hash"] = generate_hash(entry_data)
	return entry_data


if __name__ == "__main__":
	mock_record = {"id": "REC_001", "patient": "Sunita", "bp": "110/70"}
	entry = create_audit_entry(mock_record, "worker_meena")
	print("Audit Entry Created Successfully!")
	print(f"Current Hash: {entry['hash']}")
