"""
app/agents/anomaly.py — Agent 5: Anomaly Detection Agent for Nirvaah AI.

Detects suspicious submission patterns using two complementary approaches:
1. Trained scikit-learn Isolation Forest ML model
2. Hard-coded rule checks for physically impossible patterns

Inserts alerts into Supabase for the supervisor dashboard.
"""

from dotenv import load_dotenv
load_dotenv()

import os
import json
import math
from datetime import datetime, timezone, timedelta
import joblib
import numpy as np
from pathlib import Path
from supabase import create_client, Client
from app.state import PipelineState

# ----------------------------------------------------------------
# SUPABASE CLIENT (lazy initialization)
# ----------------------------------------------------------------
_supabase_client: Client | None = None


def get_supabase() -> Client:
    global _supabase_client
    if _supabase_client is None:
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        if not url or not key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
        _supabase_client = create_client(url, key)
    return _supabase_client


# ----------------------------------------------------------------
# MODEL LOADING
# Load model files at module startup — NOT on every request.
# Loading pickle files is slow (~200ms). Loading once at startup means
# the model lives in memory and scoring takes under 5ms per submission.
# ----------------------------------------------------------------

MODELS_DIR = Path(__file__).parent.parent / "models"


def load_models():
    """
    Load the Isolation Forest model, scaler, and feature columns.
    Returns (model, scaler, feature_columns) or (None, None, None)
    if files do not exist yet (before training script is run).
    """
    model_path = MODELS_DIR / "anomaly_model.pkl"
    scaler_path = MODELS_DIR / "anomaly_scaler.pkl"
    features_path = MODELS_DIR / "feature_columns.json"

    if not all([model_path.exists(), scaler_path.exists(), features_path.exists()]):
        print("[ANOMALY WARNING] Model files not found. Run scripts/train_anomaly_model.py first.")
        print("ML scoring will be skipped until model files exist.")
        return None, None, None

    model = joblib.load(model_path)
    scaler = joblib.load(scaler_path)
    with open(features_path) as f:
        feature_columns = json.load(f)

    print(f"[ANOMALY OK] Isolation Forest model loaded. Features: {feature_columns}")
    return model, scaler, feature_columns


# Module-level variables — loaded once, reused forever
anomaly_model, anomaly_scaler, feature_columns = load_models()


# ----------------------------------------------------------------
# FEATURE EXTRACTION
# ----------------------------------------------------------------

# Neutral feature vector — used when Supabase is unavailable or errors occur
NEUTRAL_FEATURES = {
    "records_per_day": 5.0,
    "avg_records_per_hour": 1.0,
    "stddev_bp_systolic": 10.0,
    "stddev_hemoglobin": 1.0,
    "unique_beneficiaries_ratio": 1.0
}


def extract_features(validated_fields: dict, sender_phone: str) -> dict:
    """
    Queries Supabase for today's submission history for this worker
    and computes the feature vector the ML model expects.
    """
    try:
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        ).isoformat()

        response = get_supabase().table("records") \
            .select("extracted_data, created_at") \
            .eq("worker_phone", sender_phone) \
            .gte("created_at", today_start) \
            .execute()

        today_records = response.data or []

        # records_per_day
        records_per_day = float(len(today_records) + 1)

        # avg_records_per_hour
        if len(today_records) < 2:
            avg_records_per_hour = 1.0
        else:
            first_time = datetime.fromisoformat(today_records[0]["created_at"])
            hours_elapsed = (datetime.now(timezone.utc) - first_time).total_seconds() / 3600
            avg_records_per_hour = records_per_day / max(hours_elapsed, 0.1)

        # stddev_bp_systolic
        bp_values = []
        for rec in today_records:
            ed = rec.get("extracted_data", {})
            if isinstance(ed, str):
                ed = json.loads(ed)
            bp = ed.get("bp_systolic")
            if bp is not None:
                bp_values.append(float(bp))
        current_bp = validated_fields.get("bp_systolic")
        if current_bp is not None:
            bp_values.append(float(current_bp))
        stddev_bp_systolic = float(np.std(bp_values)) if len(bp_values) >= 2 else 10.0

        # stddev_hemoglobin
        hb_values = []
        for rec in today_records:
            ed = rec.get("extracted_data", {})
            if isinstance(ed, str):
                ed = json.loads(ed)
            hb = ed.get("hemoglobin")
            if hb is not None:
                hb_values.append(float(hb))
        current_hb = validated_fields.get("hemoglobin")
        if current_hb is not None:
            hb_values.append(float(current_hb))
        stddev_hemoglobin = float(np.std(hb_values)) if len(hb_values) >= 2 else 1.0

        # unique_beneficiaries_ratio
        names = []
        for rec in today_records:
            ed = rec.get("extracted_data", {})
            if isinstance(ed, str):
                ed = json.loads(ed)
            name = ed.get("beneficiary_name")
            if name:
                names.append(name)
        current_name = validated_fields.get("beneficiary_name")
        if current_name:
            names.append(current_name)
        unique_beneficiaries_ratio = len(set(names)) / len(names) if names else 1.0

        return {
            "records_per_day": records_per_day,
            "avg_records_per_hour": avg_records_per_hour,
            "stddev_bp_systolic": stddev_bp_systolic,
            "stddev_hemoglobin": stddev_hemoglobin,
            "unique_beneficiaries_ratio": unique_beneficiaries_ratio
        }

    except Exception as e:
        print(f"[ANOMALY] Feature extraction failed: {e}")
        return dict(NEUTRAL_FEATURES)


# ----------------------------------------------------------------
# ML SCORING
# ----------------------------------------------------------------

def score_with_ml(features: dict) -> float:
    """Score the feature vector using the Isolation Forest model."""
    if anomaly_model is None:
        return 0.0  # skip ML scoring gracefully

    X = np.array([[features[col] for col in feature_columns]])
    X_scaled = anomaly_scaler.transform(X)

    # decision_function: more negative = more anomalous
    raw_score = anomaly_model.decision_function(X_scaled)[0]

    # Convert to 0.0-1.0 where 1.0 = most anomalous
    # -0.5 (very anomalous) → 1.0
    #  0.0 (neutral)        → 0.5
    # +0.5 (very normal)    → 0.0
    normalized = 1.0 - (raw_score + 0.5) / 1.0
    return float(max(0.0, min(1.0, normalized)))


# ----------------------------------------------------------------
# HARD RULE CHECKS
# ----------------------------------------------------------------

def check_gps_impossibility(sender_phone: str) -> str | None:
    """Rule 1: GPS impossibility — 30+ km in under 15 minutes."""
    try:
        response = get_supabase().table("records") \
            .select("extracted_data, created_at") \
            .eq("worker_phone", sender_phone) \
            .order("created_at", desc=True) \
            .limit(2) \
            .execute()

        records = response.data or []
        if len(records) < 2:
            return None

        def get_gps(rec):
            ed = rec.get("extracted_data", {})
            if isinstance(ed, str):
                ed = json.loads(ed)
            lat = ed.get("latitude") or ed.get("lat")
            lon = ed.get("longitude") or ed.get("lon")
            if lat is None or lon is None:
                return None
            return (float(lat), float(lon))

        gps1 = get_gps(records[0])
        gps2 = get_gps(records[1])
        if gps1 is None or gps2 is None:
            return None

        # Haversine distance
        lat1, lon1 = gps1
        lat2, lon2 = gps2
        R = 6371  # Earth radius in km
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(dlon / 2) ** 2)
        distance_km = 2 * R * math.asin(math.sqrt(a))

        # Time difference
        t1 = datetime.fromisoformat(records[0]["created_at"])
        t2 = datetime.fromisoformat(records[1]["created_at"])
        time_diff_minutes = abs((t1 - t2).total_seconds()) / 60

        if distance_km > 30 and time_diff_minutes < 15:
            return "gps_impossibility"

        return None
    except Exception:
        return None


def check_submission_velocity(sender_phone: str) -> str | None:
    """Rule 2: More than 1 submission in the last 90 seconds."""
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(seconds=90)).isoformat()
        response = get_supabase().table("records") \
            .select("id") \
            .eq("worker_phone", sender_phone) \
            .gte("created_at", cutoff) \
            .execute()

        if len(response.data or []) > 1:
            return "high_submission_velocity"
        return None
    except Exception:
        return None


def check_field_duplication(validated_fields: dict) -> str | None:
    """Rule 3: Identical BP readings for different beneficiaries today."""
    try:
        bp_sys = validated_fields.get("bp_systolic")
        bp_dia = validated_fields.get("bp_diastolic")
        name = validated_fields.get("beneficiary_name")
        if bp_sys is None or bp_dia is None or name is None:
            return None

        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        ).isoformat()

        response = get_supabase().table("records") \
            .select("id") \
            .gte("created_at", today_start) \
            .eq("extracted_data->>bp_systolic", str(bp_sys)) \
            .eq("extracted_data->>bp_diastolic", str(bp_dia)) \
            .neq("extracted_data->>beneficiary_name", name) \
            .execute()

        if response.data:
            return "duplicate_clinical_values"
        return None
    except Exception:
        return None


def check_off_hours() -> str | None:
    """Rule 4: Submission between 11 PM and 5 AM IST. Soft flag only."""
    ist_offset = timedelta(hours=5, minutes=30)
    ist_now = datetime.now(timezone.utc) + ist_offset
    if ist_now.hour >= 23 or ist_now.hour < 5:
        return "off_hours_submission"
    return None


# ----------------------------------------------------------------
# ALERT INSERTION
# ----------------------------------------------------------------

def insert_alert(
    record_id: str,
    worker_phone: str,
    flag_type: str,
    anomaly_score: float,
    severity: str
):
    """Insert alert row into Supabase. Never crashes the pipeline."""
    try:
        get_supabase().table("alerts").insert({
            "record_id": record_id,
            "worker_phone": worker_phone,
            "flag_type": flag_type,
            "anomaly_score": anomaly_score,
            "severity": severity,
            "dismissed": False,
            "created_at": datetime.now(timezone.utc).isoformat()
        }).execute()
    except Exception as e:
        print(f"[ANOMALY] Alert insertion failed: {e}")


# ----------------------------------------------------------------
# MAIN ANOMALY DETECTION
# ----------------------------------------------------------------

def run_anomaly_detection(
    validated_fields: dict,
    sender_phone: str,
    record_id: str
) -> tuple[float, list]:
    """
    Combines ML scoring and rule checks.
    Returns (anomaly_score, flags).
    """
    # Step 1 — Extract features and ML score
    features = extract_features(validated_fields, sender_phone)
    ml_score = score_with_ml(features)

    # Step 2 — Run all hard rule checks
    flags = []
    for check_fn, args in [
        (check_gps_impossibility, [sender_phone]),
        (check_submission_velocity, [sender_phone]),
        (check_field_duplication, [validated_fields]),
        (check_off_hours, [])
    ]:
        result = check_fn(*args)
        if result is not None:
            flags.append(result)

    # Step 3 — Determine final score
    threshold = float(os.environ.get("ANOMALY_THRESHOLD", "0.6"))
    hard_rule_triggered = len([f for f in flags if f != "off_hours_submission"]) > 0

    if hard_rule_triggered:
        final_score = max(ml_score, 0.85)
    else:
        final_score = ml_score

    # Step 4 — Insert alerts if warranted
    if final_score > threshold or hard_rule_triggered:
        severity = "high" if final_score > 0.8 else "medium"
        primary_flag = flags[0] if flags else "ml_anomaly"
        insert_alert(record_id, sender_phone, primary_flag, final_score, severity)

    if "off_hours_submission" in flags and final_score <= threshold:
        insert_alert(record_id, sender_phone, "off_hours_submission",
                     final_score, "low")

    return (final_score, flags)


# ----------------------------------------------------------------
# LANGGRAPH NODE
# ----------------------------------------------------------------

def anomaly_node(state: PipelineState) -> dict:
    """
    LangGraph node for Agent 5 — Anomaly Detection Agent.

    Combines ML scoring and hard rule checks to detect suspicious
    submission patterns. Inserts alerts into Supabase for the
    supervisor dashboard to pick up via Realtime subscription.
    """
    validated_fields = state.get("validated_fields", {})
    sender_phone = state.get("sender_phone", "")
    record_id = state.get("sync_status", {}).get("record_id", "")

    if not validated_fields:
        return {
            "anomaly_score": 0.0,
            "anomaly_flags": [],
            "errors": state.get("errors", []) + ["anomaly: no validated fields"]
        }

    try:
        score, flags = run_anomaly_detection(
            validated_fields, sender_phone, record_id
        )
        return {
            "anomaly_score": score,
            "anomaly_flags": flags,
            "errors": state.get("errors", [])
        }

    except Exception as e:
        # Anomaly detection failure must NEVER block the pipeline.
        return {
            "anomaly_score": 0.0,
            "anomaly_flags": [],
            "errors": state.get("errors", []) + [f"anomaly: {str(e)}"]
        }
