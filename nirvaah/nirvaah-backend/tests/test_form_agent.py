"""
tests/test_form_agent.py — Tests for Agent 3 (Form Agent).

Tests schema mapping, derived field computation, metadata, unknown visit
type fallback, and full LangGraph pipeline integration.

Run with:
    cd nirvaah/nirvaah-backend
    python tests/test_form_agent.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from app.agents.form_agent import map_to_forms

SAMPLE_VALIDATED = {
    "visit_type": "anc_visit",
    "beneficiary_name": "Sunita Thomas",
    "bp_systolic": 118,
    "bp_diastolic": 76,
    "hemoglobin": 10.2,
    "weight_kg": 64.0,
    "iron_tablets_given": 30,
    "next_visit_date": "20",
    "next_visit_location": "PHC",
    "referred": False,
    "overall_confidence": 0.95,
    "field_confidence": {"bp_systolic": 0.95, "hemoglobin": 0.90}
}


def test_f1_hmis_mapping():
    """F1 — HMIS mapping correctness."""
    result = map_to_forms(SAMPLE_VALIDATED)
    hmis = result["hmis"]
    assert hmis.get("ANC_BP_SYS") == 118, f"Expected 118, got {hmis.get('ANC_BP_SYS')}"
    assert hmis.get("ANC_HB") == 10.2, f"Expected 10.2, got {hmis.get('ANC_HB')}"
    assert hmis.get("ANC_IFA") == 30, f"Expected 30, got {hmis.get('ANC_IFA')}"
    print(f"✓ F1 PASS — HMIS: BP_SYS={hmis['ANC_BP_SYS']}, HB={hmis['ANC_HB']}, IFA={hmis['ANC_IFA']}")


def test_f2_mcts_mapping():
    """F2 — MCTS mapping correctness."""
    result = map_to_forms(SAMPLE_VALIDATED)
    mcts = result["mcts"]
    assert mcts.get("beneficiary_name") == "Sunita Thomas", f"Got: {mcts.get('beneficiary_name')}"
    assert mcts.get("next_visit_date") == "20", f"Got: {mcts.get('next_visit_date')}"
    assert mcts.get("hemoglobin") == 10.2, f"Got: {mcts.get('hemoglobin')}"
    print(f"✓ F2 PASS — MCTS: name={mcts['beneficiary_name']}, next_visit={mcts['next_visit_date']}")


def test_f3_kerala_hims_derived():
    """F3 — Kerala HIMS derived fields."""
    result = map_to_forms(SAMPLE_VALIDATED)
    kh = result["kerala_hims"]
    assert kh.get("hb_status") == "low", f"Expected 'low', got: {kh.get('hb_status')}"
    assert kh.get("anemia_grade") == "mild", f"Expected 'mild', got: {kh.get('anemia_grade')}"
    assert kh.get("bp_category") == "normal", f"Expected 'normal', got: {kh.get('bp_category')}"
    print(f"✓ F3 PASS — Kerala HIMS: hb_status={kh['hb_status']}, anemia={kh['anemia_grade']}, bp={kh['bp_category']}")


def test_f4_metadata():
    """F4 — Metadata fields present."""
    result = map_to_forms(SAMPLE_VALIDATED)
    assert result["hmis"]["_visit_type"] == "anc_visit", f"Got: {result['hmis'].get('_visit_type')}"
    assert result["mcts"]["_destination"] == "MCTS", f"Got: {result['mcts'].get('_destination')}"
    assert result["kerala_hims"]["_destination"] == "Kerala_HIMS"
    print(f"✓ F4 PASS — Metadata: hmis._visit_type=anc_visit, mcts._destination=MCTS")


def test_f5_unknown_visit_type():
    """F5 — Unknown visit type defaults to anc_visit."""
    unknown_input = {**SAMPLE_VALIDATED, "visit_type": "unknown_type"}
    result = map_to_forms(unknown_input)
    assert "ANC_BP_SYS" in result["hmis"], f"Expected ANC_BP_SYS in hmis, got: {list(result['hmis'].keys())}"
    print(f"✓ F5 PASS — Unknown visit type defaulted to anc_visit")


def test_f6_full_pipeline():
    """F6 — Full pipeline with all three agents (requires GROQ_API_KEY)."""
    from app.pipeline import run_pipeline

    result = asyncio.run(run_pipeline(
        sender_phone="+919876543210",
        text="Sunita Thomas visit. BP 118/76. Hemoglobin 10.2. Weight 64kg. Iron tablets 30. Next visit 20th PHC."
    ))

    hmis = result.get("mapped_forms", {}).get("hmis", {})
    kh = result.get("mapped_forms", {}).get("kerala_hims", {})

    assert hmis.get("ANC_BP_SYS") == 118, f"Expected HMIS ANC_BP_SYS=118, got: {hmis.get('ANC_BP_SYS')}"
    assert kh.get("hb_status") == "low", f"Expected hb_status='low', got: {kh.get('hb_status')}"
    assert result.get("pipeline_complete") == True, f"Expected pipeline_complete=True"
    print(f"✓ F6 PASS — Full pipeline: HMIS BP={hmis.get('ANC_BP_SYS')}, Kerala hb={kh.get('hb_status')}, complete={result.get('pipeline_complete')}")


def main():
    print("=" * 60)
    print("NIRVAAH AI — Form Agent Tests")
    print("=" * 60)

    test_f1_hmis_mapping()
    test_f2_mcts_mapping()
    test_f3_kerala_hims_derived()
    test_f4_metadata()
    test_f5_unknown_visit_type()

    print("\n" + "-" * 60)
    print("Running F6 — full LangGraph pipeline (requires GROQ_API_KEY)...")
    print("-" * 60)
    test_f6_full_pipeline()

    print("\n" + "=" * 60)
    print("All form agent tests complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
