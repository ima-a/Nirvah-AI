import hashlib
import json
from datetime import datetime, timezone
from app.constants import HASH_PREFIX, GENESIS_HASH

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


# ============================================================
# PIPELINE COMPATIBILITY WRAPPER
# Called by the LangGraph audit_node in pipeline.py
# Bridges the pipeline's (record, worker_id) call signature
# to the cyber implementation's (record_id, payload, prev_hash)
# ============================================================

from app.database import supabase

INCENTIVE_THRESHOLDS = {
    'anc_visit': 4,       # 4 ANC visits triggers JSY incentive
    'pnc_visit': 3,       # 3 PNC visits
    'immunisation_visit': 6,  # Complete immunisation schedule
}

def create_audit_entry_for_pipeline(record: dict, worker_id: str) -> dict:
    """
    Pipeline-facing wrapper. Called by audit_node in pipeline.py.
    Fetches the previous hash from Supabase, then calls the
    cyber team's create_audit_entry() with the correct arguments.
    """
    # Fetch previous hash from audit_log
    try:
        prev = supabase.table('audit_log') \
            .select('hash') \
            .order('id', desc=True) \
            .limit(1) \
            .execute()
        previous_hash = prev.data[0]['hash'] if prev.data else GENESIS_HASH
    except Exception:
        previous_hash = GENESIS_HASH

    record_id = record.get('id', f"NV-{record.get('beneficiary_id', 'UNKNOWN')}")

    # Call cyber team's implementation
    entry = create_audit_entry(record_id, record, previous_hash)

    # Write to Supabase audit_log table
    try:
        supabase.table('audit_log').insert({
            'record_id':      record_id,
            'worker_id':      worker_id,
            'timestamp':      entry['timestamp'],
            'previous_hash':  entry['previous_hash'],
            'payload_hash':   entry['payload_hash'],
            'hash':           entry['hash'],
            'record_snapshot': json.dumps(record, sort_keys=True)
        }).execute()
    except Exception as e:
        print(f"[AUDIT] Supabase write failed: {e}")

    # Check incentive threshold
    _check_and_trigger_incentive(record, worker_id)

    return entry


def _check_and_trigger_incentive(record: dict, worker_id: str):
    """
    Proof-of-service auto-trigger. Fires when a worker's verified
    visit count crosses the threshold for JSY / PNC / immunisation
    incentive eligibility. Described in Stage 8 of the build reference.
    """
    visit_type = record.get('visit_type')
    threshold = INCENTIVE_THRESHOLDS.get(visit_type)
    if not threshold:
        return

    try:
        count = supabase.table('records') \
            .select('id', count='exact') \
            .eq('beneficiary_id', record.get('beneficiary_id', '')) \
            .eq('visit_type', visit_type) \
            .execute()

        if count.count >= threshold:
            supabase.table('alerts').insert({
                'worker_id':     worker_id,
                'flag_type':     'incentive_due',
                'severity':      'low',
                'flag_reason':   f"Worker {worker_id} eligible for {visit_type} incentive — {threshold} verified visits completed",
                'beneficiary_id': record.get('beneficiary_id')
            }).execute()
            print(f"[AUDIT] Incentive trigger fired for worker {worker_id}, visit_type {visit_type}")
    except Exception as e:
        print(f"[AUDIT] Incentive check failed: {e}")
