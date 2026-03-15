from datetime import datetime
import constants

def check_hard_rules(record: dict, previous_submissions: list) -> list:
    """
    Law #5: Detect fraud patterns before they enter the permanent record.
   
    """
    alerts = []
    
    # 1. Submission Velocity Check 
    if previous_submissions:
        # Get timestamp of the most recent submission
        last_ts = datetime.fromisoformat(previous_submissions[0]['timestamp'])
        now = datetime.now()
        diff = (now - last_ts).total_seconds()
        
        if diff < 90:
            alerts.append({
                "flag_type": "SPEED_ANOMALY",
                "severity": "MEDIUM",
                "flag_reason": f"Submission received {int(diff)}s after previous entry (Threshold: 90s)."
            })

    # 2. Off-Hours Submission Check (11 PM - 5 AM) 
    current_hour = datetime.now().hour
    if current_hour >= 23 or current_hour < 5:
        alerts.append({
            "flag_type": "OFF_HOURS",
            "severity": "LOW",
            "flag_reason": "Submission made between 11 PM and 5 AM (Manual review recommended)."
        })

    # 3. Exact Duplicate Detection 
    for prev in previous_submissions:
        if (prev.get('bp_systolic') == record.get('bp_systolic') and 
            prev.get('bp_diastolic') == record.get('bp_diastolic') and
            prev.get('hemoglobin') == record.get('hemoglobin')):
            alerts.append({
                "flag_type": "EXACT_DUPLICATE",
                "severity": "HIGH",
                "flag_reason": "Duplicate medical values detected for this beneficiary today."
            })
            
    return alerts

def check_incentive_trigger(visit_count: int, visit_type: str):
    """
    Law: Proof-of-service automatic payment trigger.
    [cite: 301, 307, 331]
    """
    thresholds = {
        "anc_visit": 4,   # 4 ANC visits triggers JSY [cite: 308]
        "pnc_visit": 3,   # 3 PNC visits [cite: 309]
        "immunisation": 6 # Complete schedule [cite: 310]
    }
    
    required = thresholds.get(visit_type.lower())
    if required and visit_count >= required:
        return {
            "flag_type": "incentive_due",
            "severity": "low",
            "flag_reason": f"Incentive threshold reached: {visit_count} verified {visit_type} visits."
        }
    return None

# --- Quick Test ---
if __name__ == "__main__":
    # Mock a new record
    new_record = {"bp_systolic": 120, "bp_diastolic": 80, "hemoglobin": 10.5, "beneficiary_id": "B1"}
    
    # Mock a previous submission from 30 seconds ago
    mock_prev = [{"timestamp": datetime.now().isoformat(), "bp_systolic": 120, "bp_diastolic": 80, "hemoglobin": 10.5}]
    
    # Run checks
    found_alerts = check_hard_rules(new_record, mock_prev)
    
    print("--- LOG-06 Anomaly Detection Test ---")
    for alert in found_alerts:
        print(f"[{alert['severity'].upper()}] {alert['flag_type']}: {alert['flag_reason']}")
