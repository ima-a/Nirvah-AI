"""
Agent 1 — Intent / Extraction Agent
Receives a raw ASHA-worker transcript (Malayalam / English / mixed) and
returns a structured dict of medical fields via a CrewAI agent backed by
the Grok (xAI) LLM.
"""

import json
import os
from pathlib import Path
from typing import Any, Optional, Type

from crewai import Agent, Crew, LLM, Process, Task
from crewai.tools import BaseTool
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel

load_dotenv()

_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
_PROMPT_PATH = _BACKEND_ROOT / "data" / "extraction_prompt.txt"


def _get_grok_api_key() -> Optional[str]:
    """Prefer GROK_API_KEY; keep XAI_API_KEY fallback for compatibility."""
    return os.getenv("GROK_API_KEY") or os.getenv("XAI_API_KEY")


def _build_llm() -> LLM:
    api_key = _get_grok_api_key()
    if not api_key:
        raise RuntimeError("missing_grok_api_key")

    return LLM(
        model="xai/grok-3",
        api_key=api_key,
        base_url="https://api.x.ai/v1",
        temperature=0.1,
    )


class _TranscriptInput(BaseModel):
    transcript: str


class MedicalExtractionTool(BaseTool):
    """Call Grok with the extraction prompt and return a JSON string."""

    name: str = "MedicalExtractionTool"
    description: str = (
        "Extracts structured medical fields from an ASHA worker transcript. "
        "Input: raw transcript text (string). "
        "Output: JSON string containing all extractable medical fields."
    )
    args_schema: Type[BaseModel] = _TranscriptInput
    _client: Optional[Any] = None

    def _get_client(self) -> OpenAI:
        if self._client is None:
            api_key = _get_grok_api_key()
            if not api_key:
                raise RuntimeError("missing_grok_api_key")

            self._client = OpenAI(
                api_key=api_key,
                base_url="https://api.x.ai/v1",
            )
        return self._client

    def _run(self, transcript: str) -> str:  # type: ignore[override]
        system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")

        client = self._get_client()
        response = client.chat.completions.create(
            model="grok-3",
            temperature=0.1,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": transcript},
            ],
        )
        raw = response.choices[0].message.content or ""

        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        try:
            json.loads(raw)
            return raw
        except json.JSONDecodeError:
            fallback = {
                "overall_confidence": 0.0,
                "field_confidence": {},
                "error": "json_parse_failed",
                "raw_response": raw[:500],
            }
            return json.dumps(fallback)


def create_extraction_agent() -> Agent:
    return Agent(
        role="Medical Data Extraction Specialist",
        goal=(
            "Extract every medical field present in ASHA worker transcripts "
            "with maximum accuracy. Return clean, structured JSON with "
            "confidence scores for every extracted field."
        ),
        backstory=(
            "You are an expert in Kerala public health systems, HMIS/MCTS data "
            "standards, and maternal-child health records. You have deep "
            "familiarity with Malayalam medical vocabulary, code-switching between "
            "Malayalam and English, and the specific data fields required by the "
            "National Health Mission. You never fabricate data; if a field is not "
            "present in the transcript, you return null for that field."
        ),
        tools=[MedicalExtractionTool()],
        llm=_build_llm(),
        verbose=True,
        allow_delegation=False,
    )


def create_extraction_task(agent: Agent, transcript: str) -> Task:
    return Task(
        description=(
            f"Process the following ASHA worker transcript using your "
            f"MedicalExtractionTool and return the JSON output exactly as "
            f"received from the tool. Do not modify the JSON in any way.\n\n"
            f"TRANSCRIPT:\n{transcript}"
        ),
        expected_output=(
            "A valid JSON string containing all extractable medical fields "
            "from the transcript, including overall_confidence and field_confidence scores."
        ),
        agent=agent,
    )


async def extract_fields(transcript: str) -> dict:
    if not transcript or not transcript.strip():
        return {"confidence": 0.0, "error": "empty_transcript"}

    if not _get_grok_api_key():
        return {"confidence": 0.0, "error": "missing_grok_api_key"}

    agent = create_extraction_agent()
    task = create_extraction_task(agent, transcript)

    crew = Crew(
        agents=[agent],
        tasks=[task],
        process=Process.sequential,
        verbose=True,
    )

    result = crew.kickoff()
    raw_output = getattr(result, "raw", None) or str(result)

    raw_output = raw_output.strip()
    if raw_output.startswith("```"):
        raw_output = raw_output.split("```")[1]
        if raw_output.startswith("json"):
            raw_output = raw_output[4:]
        raw_output = raw_output.strip()

    try:
        return json.loads(raw_output)
    except (json.JSONDecodeError, ValueError):
        return {"confidence": 0.0, "error": "crew_output_parse_failed"}
