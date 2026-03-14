"""
tests/test_pipeline.py — End-to-end test for the LangGraph pipeline.
Runs a real transcript through the full graph and prints state at each stage.
"""

import asyncio
import sys
from pathlib import Path

# Ensure nirvaah-backend/ is on the path when running directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from app.pipeline import run_pipeline


async def test_full_pipeline():
    print("=" * 60)
    print("Testing full LangGraph pipeline end-to-end")
    print("=" * 60)

    result = await run_pipeline(
        sender_phone="+919876543210",
        text="Sunita Thomas visit done. BP 118/76. Hemoglobin 11.4. Weight 64kg. Iron tablets 30. Next visit 20th PHC."
    )

    print(f"\ninput_source:        {result.get('input_source')}")
    print(f"extracted bp:        {result.get('extracted_fields', {}).get('bp_systolic')}")
    print(f"overall_confidence:  {result.get('extracted_fields', {}).get('overall_confidence')}")
    print(f"clarification_needed:{result.get('clarification_needed')}")
    print(f"pipeline_complete:   {result.get('pipeline_complete')}")
    print(f"errors:              {result.get('errors')}")
    print(f"\n[STUB nodes ran] validated_fields, mapped_forms, sync_status, anomaly, insights all stubbed.")
    print("Replace stubs one by one as each agent is built.")


if __name__ == "__main__":
    asyncio.run(test_full_pipeline())
