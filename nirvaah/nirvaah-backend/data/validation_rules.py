"""
data/validation_rules.py — Medical validation rules for Nirvaah AI.

Pure Python module — no AI, no API calls.
Contains the medical knowledge that the validation agent enforces.

Range values based on Kerala ASHA worker field recording standards
and WHO/NHM clinical guidelines for maternal and child health.
"""

VALIDATION_RULES = {
    "bp_systolic": {
        "min": 70,
        "max": 180,
        "alert_low": 90,       # below this = shock alert
        "alert_high": 140,     # above this = hypertension alert
        "unit": "mmHg",
        "required": True
    },
    "bp_diastolic": {
        "min": 40,
        "max": 120,
        "alert_high": 90,      # above this + systolic >140 = pre-eclampsia risk
        "unit": "mmHg",
        "required": True
    },
    "hemoglobin": {
        "min": 5.0,
        "max": 18.0,
        "alert_low": 11.0,     # below this = anemia flag
        "alert_critical": 7.0, # below this = severe anemia alert
        "unit": "g/dL",
        "required": True
    },
    "weight_kg": {
        "min": 30.0,
        "max": 150.0,
        "unit": "kg",
        "required": False
    },
    "iron_tablets_given": {
        "min": 0,
        "max": 100,
        "unit": "tablets",
        "required": False
    },
    "gestational_age_weeks": {
        "min": 4,
        "max": 42,
        "alert_high": 42,      # above this = overdue alert
        "unit": "weeks",
        "required": False
    },
    "baby_weight_kg": {
        "min": 0.5,
        "max": 6.0,
        "alert_low": 2.5,      # below this = low birth weight flag
        "unit": "kg",
        "required": False
    }
}

REQUIRED_FIELDS_BY_VISIT_TYPE = {
    "anc_visit": ["bp_systolic", "bp_diastolic", "hemoglobin", "weight_kg"],
    "pnc_visit": ["bp_systolic", "bp_diastolic"],
    "immunisation_visit": ["vaccines_given"],
    "family_planning_visit": ["beneficiary_name"]
}
