"""
tests/test_validation.py — Comprehensive tests for Agent 2 (Validation Agent).

Tests range checks, confidence thresholds, clinical alerts, clarification
flow, and full LangGraph pipeline integration.

Run with:
    cd nirvaah/nirvaah-backend
    python tests/test_validation.py
"""

import asyncio
import sys
from pathlib import Path

# Ensure nirvaah-backend/ is on the path when running directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from app.agents.validation import validate_fields, run_range_checks, check_confidence, ClarificationRequired


def test_v1_normal_anc():
    """V1 — Normal valid ANC visit (should pass with no alerts)."""
    input_data = {
        "visit_type": "anc_visit",
        "bp_systolic": 110, "bp_diastolic": 70,
        "hemoglobin": 11.5, "weight_kg": 62.0,
        "overall_confidence": 0.95,
        "field_confidence": {"bp_systolic": 0.95, "hemoglobin": 0.95}
    }

    try:
        result = validate_fields(input_data)
        alerts = result.get("validation_alerts", [])
        assert len(alerts) == 0, f"Expected no alerts, got: {alerts}"
        print("✓ V1 PASS — Normal ANC visit validated cleanly")
    except ClarificationRequired as e:
        print(f"✗ V1 FAIL — Unexpected clarification: {e.field}")


def test_v2_impossible_bp():
    """V2 — Impossible BP value (should replace with None and request clarification)."""
    input_data = {
        "visit_type": "anc_visit",
        "bp_systolic": 999, "bp_diastolic": 70,
        "hemoglobin": 11.0, "weight_kg": 60.0,
        "overall_confidence": 0.90,
        "field_confidence": {"bp_systolic": 0.90}
    }

    try:
        result = validate_fields(input_data)
        print(f"✗ V2 FAIL — Should have raised ClarificationRequired")
    except ClarificationRequired as e:
        assert "bp_systolic" in e.field, f"Expected bp_systolic, got: {e.field}"
        assert len(e.question) > 0, "Expected non-empty question"
        print(f"✓ V2 PASS — Impossible BP caught, clarification: '{e.question[:60]}...'")


def test_v3_high_bp_alert():
    """V3 — High BP alert (valid but concerning — should NOT raise, just alert)."""
    input_data = {
        "visit_type": "anc_visit",
        "bp_systolic": 145, "bp_diastolic": 92,
        "hemoglobin": 10.5, "weight_kg": 65.0,
        "overall_confidence": 0.92,
        "field_confidence": {"bp_systolic": 0.92, "hemoglobin": 0.85}
    }

    try:
        result = validate_fields(input_data)
        alerts = result.get("validation_alerts", [])
        assert "bp_systolic_high_alert" in alerts, f"Expected bp_systolic_high_alert, got: {alerts}"
        assert "pre_eclampsia_risk" in alerts, f"Expected pre_eclampsia_risk, got: {alerts}"
        print(f"✓ V3 PASS — High BP + pre-eclampsia alerts fired: {alerts}")
    except ClarificationRequired as e:
        print(f"✗ V3 FAIL — Should NOT have raised clarification: {e.field}")


def test_v4_low_confidence():
    """V4 — Low confidence (should request clarification)."""
    input_data = {
        "visit_type": "anc_visit",
        "bp_systolic": 110, "bp_diastolic": 70,
        "hemoglobin": 10.2,
        "overall_confidence": 0.45,
        "field_confidence": {"bp_systolic": 0.45}
    }

    try:
        result = validate_fields(input_data)
        print(f"✗ V4 FAIL — Should have raised ClarificationRequired")
    except ClarificationRequired as e:
        assert len(e.question) > 0, "Expected non-empty question"
        print(f"✓ V4 PASS — Low confidence caught for: {e.field}")


def test_v5_severe_anemia():
    """V5 — Severe anemia (hemoglobin < 7.0, should alert but not block)."""
    input_data = {
        "visit_type": "anc_visit",
        "bp_systolic": 110, "bp_diastolic": 70,
        "hemoglobin": 6.2, "weight_kg": 58.0,
        "overall_confidence": 0.93,
        "field_confidence": {"hemoglobin": 0.93}
    }

    try:
        result = validate_fields(input_data)
        alerts = result.get("validation_alerts", [])
        assert "severe_anemia_critical" in alerts, f"Expected severe_anemia_critical, got: {alerts}"
        assert "hemoglobin_low_alert" in alerts, f"Expected hemoglobin_low_alert, got: {alerts}"
        print(f"✓ V5 PASS — Severe anemia alerts fired: {alerts}")
    except ClarificationRequired as e:
        print(f"✗ V5 FAIL — Should NOT have raised clarification: {e.field}")


def test_v6_full_pipeline():
    """V6 — Run through the full LangGraph pipeline with validation."""
    from app.pipeline import run_pipeline

    result = asyncio.run(run_pipeline(
        sender_phone="+919876543210",
        text="Sunita visit. BP 118/76. Hemoglobin 11.4. Weight 64kg. Iron tablets 30."
    ))

    assert result.get("clarification_needed") == False, \
        f"Expected clarification_needed=False, got: {result.get('clarification_needed')}"
    assert result.get("validated_fields"), \
        "Expected non-empty validated_fields"
    assert result.get("pipeline_complete") == True, \
        f"Expected pipeline_complete=True, got: {result.get('pipeline_complete')}"
    print(f"✓ V6 PASS — Full pipeline ran: confidence={result.get('extracted_fields', {}).get('overall_confidence')}, "
          f"complete={result.get('pipeline_complete')}")


def main():
    print("=" * 60)
    print("NIRVAAH AI — Validation Agent Tests")
    print("=" * 60)

    test_v1_normal_anc()
    test_v2_impossible_bp()
    test_v3_high_bp_alert()
    test_v4_low_confidence()
    test_v5_severe_anemia()

    print("\n" + "-" * 60)
    print("Running V6 — full LangGraph pipeline (requires GROQ_API_KEY)...")
    print("-" * 60)
    test_v6_full_pipeline()

    print("\n" + "=" * 60)
    print("All validation tests complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
