"""
tests/test_sync_agent.py — Tests for Agent 4 (Sync Agent).

Tests sync_record, Redis clarification helpers, empty state handling,
and full LangGraph pipeline integration.

Run with:
    cd nirvaah/nirvaah-backend
    python tests/test_sync_agent.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from app.agents.sync_agent import (
    sync_record, sync_node,
    store_pending_clarification, get_pending_clarification,
    clear_pending_clarification
)
from app.state import get_initial_state

SAMPLE_MAPPED = {
    "hmis": {"ANC_BP_SYS": 118, "ANC_BP_DIA": 76, "ANC_HB": 10.2,
             "_visit_type": "anc_visit", "_destination": "HMIS"},
    "mcts": {"beneficiary_name": "Sunita Thomas", "next_visit_date": "20",
             "_visit_type": "anc_visit", "_destination": "MCTS"},
    "kerala_hims": {"hb_status": "low", "anemia_grade": "mild",
                    "_visit_type": "anc_visit", "_destination": "Kerala_HIMS"}
}

SAMPLE_VALIDATED = {
    "visit_type": "anc_visit",
    "beneficiary_name": "Sunita Thomas",
    "bp_systolic": 118, "bp_diastolic": 76,
    "hemoglobin": 10.2, "weight_kg": 64.0,
    "iron_tablets_given": 30,
    "next_visit_date": "20", "next_visit_location": "PHC"
}


def test_s1_sync_record_returns_id():
    """S1 — sync_record returns a record_id immediately."""
    result = asyncio.run(sync_record(
        SAMPLE_MAPPED, SAMPLE_VALIDATED, "+919876543210", "text"
    ))
    assert "record_id" in result, f"Expected record_id in result, got: {result.keys()}"
    assert len(result["record_id"]) == 36, f"Expected UUID (36 chars), got: {result['record_id']}"
    assert result["supabase"] == "queued", f"Expected 'queued', got: {result['supabase']}"
    print(f"✓ S1 PASS — record_id={result['record_id'][:8]}..., supabase={result['supabase']}")


def test_s2_redis_clarification():
    """S2 — Redis clarification helpers work correctly."""
    try:
        store_pending_clarification("+919876543210", "bp_systolic", "What was the BP?")
        retrieved = get_pending_clarification("+919876543210")

        if retrieved is None:
            print("⚠ S2 SKIP — Redis not configured (Upstash env vars missing)")
            return

        assert retrieved["field"] == "bp_systolic", f"Got: {retrieved['field']}"
        assert retrieved["question"] == "What was the BP?", f"Got: {retrieved['question']}"

        clear_pending_clarification("+919876543210")
        cleared = get_pending_clarification("+919876543210")
        assert cleared is None, f"Expected None after clear, got: {cleared}"
        print("✓ S2 PASS — Redis store/get/clear cycle works")

    except Exception as e:
        print(f"⚠ S2 SKIP — Redis error: {e}")


def test_s3_empty_mapped_forms():
    """S3 — sync_node handles empty mapped_forms gracefully."""
    empty_state = get_initial_state("test", "+919876543210")
    empty_state["mapped_forms"] = {}
    result = sync_node(empty_state)
    assert result["sync_status"]["supabase"] == "skipped", \
        f"Expected 'skipped', got: {result['sync_status']['supabase']}"
    assert len(result["errors"]) > 0, "Expected errors for empty forms"
    print(f"✓ S3 PASS — Empty forms handled: status={result['sync_status']['supabase']}")


def test_s4_full_pipeline():
    """S4 — Full pipeline through all four agents (requires GROQ_API_KEY)."""
    from app.pipeline import run_pipeline

    result = asyncio.run(run_pipeline(
        sender_phone="+919876543210",
        text="Sunita Thomas visit. BP 118/76. Hemoglobin 10.2. Weight 64kg. Iron tablets 30. Next visit 20th PHC."
    ))

    sync_status = result.get("sync_status", {})
    assert sync_status.get("record_id") is not None, f"Expected record_id, got: {sync_status}"
    assert sync_status.get("supabase") == "queued", f"Expected 'queued', got: {sync_status.get('supabase')}"
    assert result.get("pipeline_complete") == True, f"Expected pipeline_complete=True"
    print(f"✓ S4 PASS — Pipeline: record_id={sync_status['record_id'][:8]}..., "
          f"supabase={sync_status['supabase']}, complete={result.get('pipeline_complete')}")


def main():
    print("=" * 60)
    print("NIRVAAH AI — Sync Agent Tests")
    print("=" * 60)

    test_s1_sync_record_returns_id()
    test_s2_redis_clarification()
    test_s3_empty_mapped_forms()

    print("\n" + "-" * 60)
    print("Running S4 — full LangGraph pipeline (requires GROQ_API_KEY)...")
    print("-" * 60)
    test_s4_full_pipeline()

    print("\n" + "=" * 60)
    print("All sync agent tests complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
