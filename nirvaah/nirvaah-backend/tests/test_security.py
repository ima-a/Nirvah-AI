import json
# Import your logic from the other file
from audit_chain import create_audit_entry 

# 1. Mock data from the AI Teammate's extraction
mock_pipeline_output = [
    {"id": "REC_001", "patient": "Sunita", "bp": "110/70", "hb": 10.2},
    {"id": "REC_002", "patient": "Ammu", "bp": "120/80", "hb": 12.1},
    {"id": "REC_003", "patient": "Deepa", "bp": "115/75", "hb": 11.5}
]

def run_mock_audit():
    audit_ledger = []
    # The 'Genesis' hash for the first record [cite: 290]
    last_hash = "0" * 64 
    
    print("--- Starting Mock Audit Chain ---")
    for record in mock_pipeline_output:
        # Create the entry and link it to the previous hash [cite: 281, 295]
        entry = create_audit_entry(record, "worker_meena", last_hash)
        
        audit_ledger.append(entry)
        last_hash = entry["hash"] # Move the chain forward [cite: 290]
        
        print(f"Record {record['id']} Secured.")
        print(f"  Current Hash: {entry['hash'][:10]}...")
        print(f"  Linked to Prev: {entry['previous_hash'][:10]}...\n")

    # 2. Save the mock 'Audit File' [cite: 281]
    with open("audit_ledger_test.json", "w") as f:
        json.dump(audit_ledger, f, indent=4)
    print("Mock Audit File 'audit_ledger_test.json' created successfully.")

if __name__ == "__main__":
    run_mock_audit()
