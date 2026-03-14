"""
Standalone test script for Agent 1 — extraction.py
Run from nirvaah-backend/:
    python tests/test_extraction.py

Tests extract_fields() against 4 sample transcripts covering:
  1. Clear English
  2. Mixed Malayalam-English
  3. Malayalam numbers
  4. Vague / incomplete (expected low confidence)
"""

import asyncio
import sys
from pathlib import Path

# Ensure nirvaah-backend/ is on the path when running directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agents.extraction import extract_fields  # noqa: E402

# ---------------------------------------------------------------------------
# Test transcripts
# ---------------------------------------------------------------------------

TRANSCRIPTS = [
    {
        "id": 1,
        "label": "Clear English",
        "text": (
            "Sunita Thomas visit completed. BP 110 over 70, normal. "
            "Hemoglobin 10.2. 30 iron tablets given. Anemia counselling done. "
            "Next visit 14th at PHC. Weight 62 kg."
        ),
        "vague": False,
    },
    {
        "id": 2,
        "label": "Mixed Malayalam-English",
        "text": (
            "Meena-yude visit cheythu. BP 130/90 aanu, slightly high. "
            "Hemoglobin 9.5, iron tablets 30 koduthu. Thukkam 58 kg. "
            "Aduttha visit PHC-il aavandé."
        ),
        "vague": False,
    },
    {
        "id": 3,
        "label": "Malayalam numbers",
        "text": (
            "Raji-yude BP onnooro thettathu, hemoglobin pathu point anchu. "
            "IFA tablets mupathu koduthu."
        ),
        "vague": False,
    },
    {
        "id": 4,
        "label": "Vague / incomplete",
        "text": "Patient visit done. BP taken. Some tablets given.",
        "vague": True,
    },
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"
SEP = "-" * 60


def _fmt(value) -> str:
    return str(value) if value is not None else "—"


def _print_result(case: dict, result: dict) -> None:
    print(SEP)
    print(f"Test {case['id']}: {case['label']}")
    print(f"Input : {case['text'][:100]}{'...' if len(case['text']) > 100 else ''}")
    print(f"overall_confidence : {_fmt(result.get('overall_confidence', result.get('confidence')))}")
    print(f"bp_systolic        : {_fmt(result.get('bp_systolic'))}")
    print(f"bp_diastolic       : {_fmt(result.get('bp_diastolic'))}")
    print(f"hemoglobin         : {_fmt(result.get('hemoglobin'))}")
    print(f"weight_kg          : {_fmt(result.get('weight_kg'))}")
    print(f"next_visit_date    : {_fmt(result.get('next_visit_date'))}")
    if result.get("error"):
        print(f"error              : {result['error']}")


def _check(case: dict, result: dict) -> bool:
    """Return True if the test passes."""
    confidence = result.get("overall_confidence", result.get("confidence"))

    # Every result must have a confidence value
    if confidence is None:
        print(f"{RED}FAIL{RESET} — no confidence key in result")
        return False

    if case["vague"]:
        passed = float(confidence) < 0.5
        status = f"{GREEN}PASS{RESET}" if passed else f"{RED}FAIL{RESET}"
        print(f"Result : {status} (expected confidence < 0.5, got {confidence})")
        return passed
    else:
        # Non-vague transcripts: confidence key must exist (value may vary with LLM)
        print(f"Result : {GREEN}PASS{RESET} (confidence key present: {confidence})")
        return True


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


async def run_tests() -> None:
    all_passed = True
    for case in TRANSCRIPTS:
        result = await extract_fields(case["text"])
        _print_result(case, result)
        passed = _check(case, result)
        if not passed:
            all_passed = False

    print(SEP)
    if all_passed:
        print(f"{GREEN}All tests passed.{RESET}")
    else:
        print(f"{RED}One or more tests failed.{RESET}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_tests())
