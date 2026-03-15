"""
tests/test_insights.py — Test suite for Agent 6 (Insights Agent).

Tests dropout model training, risk scoring, scheme eligibility,
risk summary generation, and full end-to-end pipeline.

Run with:
    python tests/test_insights.py
"""

import sys
from pathlib import Path

# Ensure nirvaah-backend/ is on the path when running directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

import asyncio
import subprocess
import json

# Sample validated data used across all tests
sample_validated = {
    "visit_type": "anc_visit",
    "beneficiary_name": "Sunita Thomas",
    "beneficiary_age": 24,
    "bp_systolic": 118,
    "bp_diastolic": 76,
    "hemoglobin": 8.5,          # deliberately low to trigger high risk
    "weight_kg": 64.0,
    "iron_tablets_given": 30,
    "gestational_age_weeks": 18,
    "anc_visit_number": 1,
    "next_visit_date": "20",
    "next_visit_location": "PHC",
    "bpl_card": True,
    "referred": False
}


def test_i1_training_produces_model():
    """Test I1 — Training script produces model files."""
    print("\n" + "=" * 60)
    print("Test I1: Training script produces model files")
    print("=" * 60)

    result = subprocess.run(
        [sys.executable, "scripts/train_dropout_model.py"],
        capture_output=True,
        text=True
    )

    print(result.stdout)
    if result.stderr:
        print(f"STDERR: {result.stderr}")

    assert result.returncode == 0, f"Training script failed with code {result.returncode}"
    assert Path("models/dropout_model.pkl").exists(), "dropout_model.pkl not found"
    assert Path("models/dropout_feature_columns.json").exists(), "dropout_feature_columns.json not found"

    # Verify feature columns file is valid JSON
    with open("models/dropout_feature_columns.json") as f:
        cols = json.load(f)
    assert len(cols) == 10, f"Expected 10 feature columns, got {len(cols)}"

    print("[PASS] Test I1 — Model files created successfully")


def test_i2_dropout_risk_valid_float():
    """Test I2 — Dropout risk returns valid float."""
    print("\n" + "=" * 60)
    print("Test I2: Dropout risk returns valid float")
    print("=" * 60)

    # Reload the model after training
    from importlib import reload
    import app.agents.insights as insights_module
    reload(insights_module)
    from app.agents.insights import compute_dropout_risk

    risk = compute_dropout_risk(sample_validated)

    print(f"Dropout risk score: {risk:.3f}")

    assert isinstance(risk, float), f"Expected float, got {type(risk)}"
    assert 0.0 <= risk <= 1.0, f"Risk {risk} not in [0.0, 1.0]"
    assert risk > 0.4, (
        f"Risk {risk:.3f} unexpectedly low — hemoglobin 8.5 + first visit "
        f"+ BPL card should produce elevated risk"
    )

    print(f"[PASS] Test I2 — Dropout risk: {risk:.3f}")


def test_i3_scheme_eligibility():
    """Test I3 — Scheme eligibility detects correct schemes."""
    print("\n" + "=" * 60)
    print("Test I3: Scheme eligibility detects correct schemes")
    print("=" * 60)

    from data.scheme_eligibility import check_all_schemes

    schemes = check_all_schemes(sample_validated)
    scheme_names = [s["name"] for s in schemes]

    print(f"Eligible schemes: {scheme_names}")
    for s in schemes:
        print(f"  {s['name']}: {s['benefit']} — {s['reason']}")

    # anc_visit_number=1, gestational_age=18 weeks (<= 19) → PMMVY eligible
    assert "PMMVY" in scheme_names, f"PMMVY not found in {scheme_names}"

    # bpl_card=True → JSY eligible
    assert "JSY" in scheme_names, f"JSY not found in {scheme_names}"

    # universal entitlement for ANC visits
    assert "JSSK" in scheme_names, f"JSSK not found in {scheme_names}"

    # gestational_age=18 weeks (>= 16) → PMSMA eligible
    assert "PMSMA" in scheme_names, f"PMSMA not found in {scheme_names}"

    # visit_type=anc_visit, next_visit_location=PHC → Sneha Sparsham eligible
    assert "Sneha Sparsham" in scheme_names, f"Sneha Sparsham not found in {scheme_names}"

    print(f"[PASS] Test I3 — {len(schemes)} schemes detected correctly")


def test_i4_risk_summary_high_risk():
    """Test I4 — Risk summary is generated for high risk patient."""
    print("\n" + "=" * 60)
    print("Test I4: Risk summary generated for high risk patient")
    print("=" * 60)

    from importlib import reload
    import app.agents.insights as insights_module
    reload(insights_module)
    from app.agents.insights import generate_risk_summary
    from data.scheme_eligibility import check_all_schemes

    summary = generate_risk_summary(
        sample_validated,
        dropout_risk=0.82,
        eligible_schemes=check_all_schemes(sample_validated),
        anomaly_score=0.1
    )

    print(f"Risk summary: {summary}")

    assert len(summary) > 20, f"Summary too short: '{summary}'"
    assert isinstance(summary, str), f"Expected str, got {type(summary)}"

    print(f"[PASS] Test I4 — Risk summary generated ({len(summary)} chars)")


def test_i5_risk_summary_low_risk():
    """Test I5 — Risk summary is empty for low risk patient."""
    print("\n" + "=" * 60)
    print("Test I5: Risk summary empty for low risk patient")
    print("=" * 60)

    from importlib import reload
    import app.agents.insights as insights_module
    reload(insights_module)
    from app.agents.insights import generate_risk_summary

    summary = generate_risk_summary(
        sample_validated,
        dropout_risk=0.35,  # below 0.70 threshold
        eligible_schemes=[],
        anomaly_score=0.0
    )

    assert summary == "", f"Expected empty string, got: '{summary}'"

    print("[PASS] Test I5 — Risk summary correctly empty for low risk")


def test_i6_full_pipeline_e2e():
    """Test I6 — Full pipeline end-to-end through all six agents."""
    print("\n" + "=" * 60)
    print("Test I6: Full pipeline end-to-end (all 6 agents)")
    print("=" * 60)

    from app.pipeline import run_pipeline

    result = asyncio.run(run_pipeline(
        sender_phone="+919876543210",
        text=(
            "Sunita Thomas visit. BP 118/76. Hemoglobin 8.5. Weight 64kg. "
            "Iron tablets 30. Gestational age 18 weeks. First ANC visit. "
            "BPL card. Next visit 20th PHC."
        )
    ))

    # Print every field of the final state
    print("\n--- Final Pipeline State ---")
    for key, value in result.items():
        if isinstance(value, dict):
            print(f"  {key}:")
            for k, v in value.items():
                print(f"    {k}: {v}")
        elif isinstance(value, list) and value:
            print(f"  {key}:")
            for item in value:
                print(f"    - {item}")
        else:
            print(f"  {key}: {value}")

    # Assertions
    assert result["pipeline_complete"] == True, "Pipeline did not complete"
    assert 0.0 <= result["dropout_risk"] <= 1.0, f"Invalid dropout_risk: {result['dropout_risk']}"
    assert isinstance(result["eligible_schemes"], list), "eligible_schemes is not a list"
    assert result["sync_status"].get("record_id") is not None, "No record_id in sync_status"
    assert result["anomaly_score"] >= 0.0, f"Invalid anomaly_score: {result['anomaly_score']}"

    # Check form mapping worked
    hmis = result.get("mapped_forms", {}).get("hmis", {})
    if hmis.get("ANC_BP_SYS") is not None:
        assert hmis["ANC_BP_SYS"] == 118, f"Expected ANC_BP_SYS=118, got {hmis['ANC_BP_SYS']}"
        print("  ✓ HMIS BP mapping verified")

    print(f"\n[PASS] Test I6 — Full pipeline completed successfully")
    print(f"  dropout_risk:    {result['dropout_risk']:.3f}")
    print(f"  schemes:         {[s['name'] for s in result['eligible_schemes']]}")
    print(f"  risk_summary:    {'(generated)' if result['risk_summary'] else '(empty — risk below threshold)'}")
    print(f"  anomaly_score:   {result['anomaly_score']:.3f}")
    print(f"  record_id:       {result['sync_status'].get('record_id')}")
    print(f"  errors:          {result['errors']}")


def main():
    """Run all tests in order."""
    print("=" * 60)
    print("Nirvaah AI — Agent 6 (Insights) Test Suite")
    print("=" * 60)

    passed = 0
    failed = 0

    tests = [
        ("I1", test_i1_training_produces_model),
        ("I2", test_i2_dropout_risk_valid_float),
        ("I3", test_i3_scheme_eligibility),
        ("I4", test_i4_risk_summary_high_risk),
        ("I5", test_i5_risk_summary_low_risk),
        ("I6", test_i6_full_pipeline_e2e),
    ]

    for test_id, test_fn in tests:
        try:
            test_fn()
            passed += 1
        except AssertionError as e:
            print(f"\n[FAIL] Test {test_id}: {e}")
            failed += 1
        except Exception as e:
            print(f"\n[ERROR] Test {test_id}: {type(e).__name__}: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed, {passed + failed} total")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
