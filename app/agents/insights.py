"""
app/agents/insights.py — Agent 6: Insights Agent for Nirvaah AI.

The final agent in the LangGraph pipeline. Produces three outputs:
1. Dropout risk score from XGBoost model
2. Government scheme eligibility alerts
3. Human-readable risk summary from Groq (when risk is high)

Sets pipeline_complete=True when done.
"""

from dotenv import load_dotenv
load_dotenv()

import os
import json
import joblib
import numpy as np
from pathlib import Path
from datetime import datetime, timezone
from groq import Groq
from supabase import create_client, Client
from app.state import PipelineState
from data.scheme_eligibility import check_all_schemes


# ----------------------------------------------------------------
# CLIENTS
# ----------------------------------------------------------------

groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# Lazy Supabase client — avoids crash if env vars not set at import time
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
# Load XGBoost model at module startup — same reasoning as anomaly.py.
# Model loading is slow. Inference is fast. Load once, reuse forever.
# ----------------------------------------------------------------

MODELS_DIR = Path(__file__).parent.parent.parent / "models"


def load_dropout_model():
    """
    Load the XGBoost dropout prediction model, scaler, threshold, and feature columns.
    Returns (model, scaler, threshold, feature_columns) or (None, None, 0.54, None) if not found.
    """
    model_path = MODELS_DIR / "dropout_model.pkl"
    scaler_path = MODELS_DIR / "dropout_scaler.pkl"
    features_path = MODELS_DIR / "feature_columns.json"
    threshold_path = MODELS_DIR / "threshold.json"

    if not model_path.exists() or not features_path.exists():
        print("[INSIGHTS WARNING] Dropout model not found.")
        print("Run scripts/train_dropout_model.py first.")
        return None, None, 0.54, None

    model = joblib.load(model_path)

    scaler = None
    if scaler_path.exists():
        scaler = joblib.load(scaler_path)

    threshold = 0.54
    if threshold_path.exists():
        with open(threshold_path) as f:
            threshold = json.load(f).get("threshold", 0.54)

    with open(features_path) as f:
        feature_columns = json.load(f)

    print(f"[INSIGHTS OK] XGBoost dropout model loaded (threshold={threshold}).")
    return model, scaler, threshold, feature_columns


# Module-level variables — loaded once, reused forever
dropout_model, dropout_scaler, dropout_threshold, dropout_feature_columns = load_dropout_model()


# ----------------------------------------------------------------
# FEATURE BUILDING
# ----------------------------------------------------------------

def build_dropout_features(validated_fields: dict) -> dict:
    """
    Build the feature vector that the XGBoost model expects.
    Maps validated_fields to the same features in the same order
    as the training script.

    Uses safe defaults for any missing fields — the model should
    score reasonably even with incomplete data.
    """
    # mother_age: 25 is the mean age — safe neutral default
    mother_age = float(validated_fields.get("beneficiary_age") or 25.0)

    # parity: estimate from ANC visit number (imperfect but reasonable proxy)
    anc_number = validated_fields.get("anc_visit_number") or 1
    parity = float(max(0, min(3, anc_number - 1)))

    # gestational_age_first_anc: 12 weeks is reasonable first trimester default
    gestational_age_first_anc = float(
        validated_fields.get("gestational_age_weeks") or 12.0
    )

    # hemoglobin: 10.8 is the mean from training data
    hemoglobin = float(validated_fields.get("hemoglobin") or 10.8)

    # distance_to_phc_km: fixed default for demo
    # In production this would come from beneficiary registration data.
    # 3.0 km is a reasonable urban/semi-urban Kerala default.
    distance_to_phc_km = 3.0

    # anc_visits_completed: clip to 0-4
    anc_visits_completed = float(
        max(0, min(4, validated_fields.get("anc_visit_number") or 1))
    )

    # ifa_tablets_total: 30 is one month's supply — typical single visit
    ifa_tablets_total = float(validated_fields.get("iron_tablets_given") or 30)

    # scheme_enrolled: default to 0 (not enrolled) — conservative
    scheme_enrolled = 0.0

    # previous_institutional_delivery: Kerala has 99%+ institutional delivery
    previous_institutional_delivery = 1.0

    # bpl_card
    bpl_card = 1.0 if validated_fields.get("bpl_card") else 0.0

    return {
        "age_of_mother": float(validated_fields.get("beneficiary_age") or 25.0),
        "parity": float(max(0, min(3, (validated_fields.get("anc_visit_number") or 1) - 1))),
        "education_level": float(validated_fields.get("education_level") or 2),
        "distance_to_phc_km": float(validated_fields.get("distance_to_phc_km") or 3.0),
        "gestational_age_at_first_anc": float(validated_fields.get("gestational_age_weeks") or 12.0),
        "hemoglobin": float(validated_fields.get("hemoglobin") or 10.8),
        "ifa_tablets_given_total": float(validated_fields.get("iron_tablets_given") or 30),
        "previous_institutional_delivery": 1.0 if validated_fields.get("institutional_delivery") else 1.0,
        "previous_pnc_received": 1.0 if validated_fields.get("pnc_received") else 0.0,
        "pmmvy_enrolled": 1.0 if validated_fields.get("pmmvy_enrolled") else 0.0,
        "jsy_enrolled": 1.0 if validated_fields.get("jsy_enrolled") else 0.0,
        "bpl_status": 1.0 if validated_fields.get("bpl_card") else 0.0,
        "sc_st_status": 1.0 if validated_fields.get("caste_category") in ("SC", "ST") else 0.0,
        "state_code": 32.0,  # Kerala state code — model trained on NFHS-5
    }


# ----------------------------------------------------------------
# DROPOUT SCORING
# ----------------------------------------------------------------

def compute_dropout_risk(validated_fields: dict) -> float:
    """
    Compute dropout risk score using the XGBoost model.
    Returns a float between 0.0 and 1.0 (probability of dropout).
    Returns 0.0 if the model is not loaded or scoring fails.
    """
    if dropout_model is None:
        return 0.0

    try:
        features = build_dropout_features(validated_fields)

        # Build array in the scaler's exact column order
        try:
            col_order = list(dropout_scaler.feature_names_in_)
        except (AttributeError, TypeError):
            col_order = list(features.keys())
        row = [features.get(col, 0.0) for col in col_order]

        # Scale features before prediction
        if dropout_scaler is not None:
            X = dropout_scaler.transform([row])
        else:
            X = np.array([row])

        # predict_proba returns [[prob_no_dropout, prob_dropout]]
        proba = dropout_model.predict_proba(X)[0][1]
        return float(proba)

    except Exception as e:
        print(f"[INSIGHTS WARNING] Dropout scoring failed: {e}")
        return 0.0


# ----------------------------------------------------------------
# RISK SUMMARY GENERATOR
# ----------------------------------------------------------------

def generate_risk_summary(
    validated_fields: dict,
    dropout_risk: float,
    eligible_schemes: list,
    anomaly_score: float
) -> str:
    """
    Generate a human-readable risk summary using Groq.
    Only called when dropout_risk > 0.70 — otherwise returns empty string.
    """
    if dropout_risk <= 0.70:
        return ""

    # Build a context string for Groq with the key clinical facts
    scheme_names = [s["name"] for s in eligible_schemes]

    prompt = f"""
An ASHA worker just completed a health visit. Based on the data below,
write exactly 2 sentences explaining why this patient is at high risk 
of missing her next visit. Be specific about the risk factors present.
Write in simple language a community health worker can understand.
Do not use medical jargon. Do not mention scores or percentages.

Patient data:
- Hemoglobin: {validated_fields.get("hemoglobin")} g/dL
- Blood pressure: {validated_fields.get("bp_systolic")}/{validated_fields.get("bp_diastolic")} mmHg
- Gestational age: {validated_fields.get("gestational_age_weeks")} weeks
- Next visit due: {validated_fields.get("next_visit_date")} at {validated_fields.get("next_visit_location")}
- Schemes not yet enrolled in: {scheme_names if scheme_names else "none identified"}
- Dropout risk score: {dropout_risk:.2f}

Write exactly 2 sentences. No bullet points. No headings.
"""

    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=120  # 2 sentences fits comfortably in 120 tokens
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        print(f"[INSIGHTS WARNING] Risk summary generation failed: {e}")
        # Return a simple fallback rather than empty string
        # so the dashboard always shows something meaningful
        return (
            f"This patient has a high risk of missing follow-up care. "
            f"Please contact her before her next visit on "
            f"{validated_fields.get('next_visit_date', 'the scheduled date')}."
        )


# ----------------------------------------------------------------
# SUPABASE UPDATE
# ----------------------------------------------------------------

def update_beneficiary_insights(
    validated_fields: dict,
    dropout_risk: float,
    eligible_schemes: list,
    record_id: str
):
    """
    Update the beneficiaries and records tables with computed insights.
    Never raises — Supabase update failure must not crash the pipeline.
    """
    try:
        beneficiary_name = validated_fields.get("beneficiary_name")

        # Update beneficiary record if name is available
        if beneficiary_name:
            get_supabase().table("beneficiaries").update({
                "dropout_risk": dropout_risk,
                "eligible_schemes": eligible_schemes,  # stored as JSONB
                "updated_at": datetime.now(timezone.utc).isoformat()
            }).eq("beneficiary_name", beneficiary_name).execute()

        # Update the specific record with insights
        if record_id:
            get_supabase().table("records").update({
                "dropout_risk": dropout_risk,
                "eligible_schemes": eligible_schemes,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }).eq("id", record_id).execute()

    except Exception as e:
        print(f"[INSIGHTS WARNING] Supabase update failed: {e}")


# ----------------------------------------------------------------
# MAIN INSIGHTS FUNCTION
# ----------------------------------------------------------------

def run_insights(
    validated_fields: dict,
    anomaly_score: float,
    record_id: str
) -> tuple[float, list, str]:
    """
    Run all insights computations and return results.
    Returns (dropout_risk, eligible_schemes, risk_summary).
    """
    # Step 1 — Compute dropout risk
    dropout_risk = compute_dropout_risk(validated_fields)

    # Step 2 — Check scheme eligibility
    eligible_schemes = check_all_schemes(validated_fields)

    # Step 3 — Generate risk summary if high risk
    risk_summary = generate_risk_summary(
        validated_fields, dropout_risk, eligible_schemes, anomaly_score
    )

    # Step 4 — Update Supabase with insights
    update_beneficiary_insights(
        validated_fields, dropout_risk, eligible_schemes, record_id
    )

    return (dropout_risk, eligible_schemes, risk_summary)


# ----------------------------------------------------------------
# LANGGRAPH NODE
# ----------------------------------------------------------------

def insights_node(state: PipelineState) -> dict:
    """
    LangGraph node for Agent 6 — Insights Agent.

    This is the final node in the pipeline. It computes dropout risk,
    checks scheme eligibility, generates a risk summary if needed,
    updates Supabase with the insights, and sets pipeline_complete=True.

    pipeline_complete is set to True regardless of whether insights
    fully succeeded — the record is already safely in Supabase from
    Agent 4. Insights are valuable but not blocking.
    """
    validated_fields = state.get("validated_fields", {})
    anomaly_score = state.get("anomaly_score", 0.0)
    record_id = state.get("sync_status", {}).get("record_id", "")

    if not validated_fields:
        return {
            "dropout_risk": 0.0,
            "eligible_schemes": [],
            "risk_summary": "",
            "pipeline_complete": True,  # still mark complete — record is safe
            "errors": state.get("errors", []) + ["insights: no validated fields"]
        }

    try:
        dropout_risk, eligible_schemes, risk_summary = run_insights(
            validated_fields, anomaly_score, record_id
        )
        return {
            "dropout_risk": dropout_risk,
            "eligible_schemes": eligible_schemes,
            "risk_summary": risk_summary,
            "pipeline_complete": True,
            "errors": state.get("errors", [])
        }

    except Exception as e:
        # Even on complete failure, mark pipeline as complete.
        # The record exists in Supabase. Missing insights is acceptable.
        return {
            "dropout_risk": 0.0,
            "eligible_schemes": [],
            "risk_summary": "",
            "pipeline_complete": True,
            "errors": state.get("errors", []) + [f"insights: {str(e)}"]
        }
