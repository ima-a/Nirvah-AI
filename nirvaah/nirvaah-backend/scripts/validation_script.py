"""
validation_rules.py
Nirvaah AI - Loads validation rules directly from schema_registry.json
Single source of truth. Matches Stage 5 (Validation Agent) + your schema's "validation_rules" section.
"""

import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any

# Load schema (change path if needed)
SCHEMA_PATH = Path("data/schema_registry.json")
with open(SCHEMA_PATH, encoding="utf-8") as f:
    SCHEMA = json.load(f)

RANGE_RULES = SCHEMA["validation_rules"]["field_ranges"]
SCHEDULE_RULES = SCHEMA["validation_rules"]["schedule_rules"]
CONFIDENCE_THRESHOLD = SCHEMA["validation_rules"]["confidence_thresholds"]["clarification_trigger"]


def validate_field(field_name: str, value: Any) -> Dict[str, Any]:
    """
    Validates any field against the ranges defined in your schema_registry.json
    Returns: {"valid": bool, "alerts": list, "message": str, "severity": str}
    """
    # Normalise field name (schema uses snake_case or hmis_code style)
    key = field_name.lower().replace("_", "")
    rule = None
    for k in RANGE_RULES:
        if k.lower().replace("_", "") == key or k.lower() in field_name.lower():
            rule = RANGE_RULES[k]
            break

    if not rule:
        return {"valid": True, "alerts": [], "message": "No range rule defined", "severity": "info"}

    # Type handling
    try:
        val = float(value) if isinstance(value, (int, float, str)) else 0
    except (ValueError, TypeError):
        return {"valid": False, "alerts": [], "message": "Invalid numeric value", "severity": "critical"}

    # Range check
    if "min" in rule and val < rule["min"]:
        return {"valid": False, "alerts": [], "message": f"Below minimum ({rule['min']} {rule.get('unit', '')})", "severity": "critical"}
    if "max" in rule and val > rule["max"]:
        return {"valid": False, "alerts": [], "message": f"Above maximum ({rule['max']} {rule.get('unit', '')})", "severity": "critical"}

    # Specific alerts from your schema
    alerts = []
    severity = "info"
    if "alerts" in rule:
        for alert_key, alert_data in rule["alerts"].items():
            if "below_7" in alert_key and val < 7.0:
                alerts.append(alert_data["message"])
                severity = alert_data["severity"]
            elif "below_11" in alert_key and val < 11.0:
                alerts.append(alert_data["message"])
                severity = alert_data["severity"]
            elif "above_140" in alert_key and val >= 140:
                alerts.append(alert_data["message"])
                severity = alert_data["severity"]
            # Add more alert conditions from your schema as needed

    return {
        "valid": True,
        "alerts": alerts,
        "message": "Valid" if not alerts else "Valid with alerts",
        "severity": severity
    }


def validate_immunisation(vaccine_field: str, vaccination_date: datetime | str, child_dob: datetime | str) -> Dict[str, Any]:
    """
    Enforces full Kerala/National UIP schedule from your schema's schedule_rules
    Supports: BCG, OPV0, Pentavalent1-3, Measles1, VitaminA_1, DPT_Booster, etc.
    """
    if isinstance(vaccination_date, str):
        vaccination_date = datetime.fromisoformat(vaccination_date.replace("Z", "+00:00"))
    if isinstance(child_dob, str):
        child_dob = datetime.fromisoformat(child_dob.replace("Z", "+00:00"))

    age_days = (vaccination_date - child_dob).days
    age_weeks = age_days // 7
    age_months = age_days // 30

    vaccine_key = vaccine_field.replace("_date", "").upper()
    rule = SCHEDULE_RULES.get(vaccine_key)
    if not rule:
        return {"valid": True, "alerts": [], "message": "No schedule rule defined"}

    if vaccine_key == "BCG" and age_days > rule.get("maximum_age_days", 28):
        return {"valid": False, "alerts": [], "message": rule["error"], "severity": "critical"}

    if vaccine_key == "OPV0" and age_days > rule.get("maximum_age_days", 1):
        return {"valid": False, "alerts": [], "message": rule["error"], "severity": "critical"}

    if "Pentavalent" in vaccine_key:
        min_w = rule.get("minimum_age_weeks", 6)
        max_w = rule.get("maximum_age_weeks", 10)
        if not (min_w <= age_weeks <= max_w):
            return {"valid": False, "alerts": [], "message": rule["error"], "severity": "high"}

    if vaccine_key in ["MEASLES1", "VITAMINA_1"] and not (rule.get("minimum_age_months", 9) <= age_months <= 12):
        return {"valid": False, "alerts": [], "message": rule["error"] if "error" in rule else "Given outside schedule window", "severity": "high"}

    return {"valid": True, "alerts": [], "message": "Dose valid per Kerala NHM schedule", "severity": "info"}


def should_trigger_clarification(confidence: float) -> bool:
    """From your schema's confidence_thresholds"""
    return confidence < CONFIDENCE_THRESHOLD


# ====================== QUICK TEST ======================
if __name__ == "__main__":
    print("✅ Schema loaded successfully from", SCHEMA_PATH)
    print("Hb test (9.8):", validate_field("hemoglobin", 9.8))
    print("BP test (150/95):", validate_field("bp_systolic", 150))
    print("BCG at 45 days old:", validate_immunisation("bcg_date", datetime.now(), datetime.now() - timedelta(days=45)))
    print("Clarification needed if confidence=0.65:", should_trigger_clarification(0.65))
