# Agent 1: Intent / Medical Extraction Agent

## File Map
- Agent implementation: [nirvaah/nirvaah-backend/app/agents/extraction.py](../nirvaah-backend/app/agents/extraction.py)
- System prompt: [nirvaah/nirvaah-backend/data/extraction_prompt.txt](../nirvaah-backend/data/extraction_prompt.txt)
- Standalone tests: [nirvaah/nirvaah-backend/tests/test_extraction.py](../nirvaah-backend/tests/test_extraction.py)

## Purpose
Agent 1 receives a raw transcript from an ASHA voice note (Malayalam, English, or mixed), then extracts structured medical fields into JSON/dict format for downstream pipeline stages.

## Runtime Stack
- Framework: CrewAI (`Agent`, `Task`, `Crew`, `Process`)
- LLM: Grok through xAI OpenAI-compatible endpoint
- LLM temperature: `0.1` (near-deterministic extraction)
- Secrets source: `.env` loaded via `python-dotenv`

## Public API
### `extract_fields(transcript: str) -> dict`
Main async entrypoint used by the pipeline.

Behavior:
- Returns `{ "confidence": 0.0, "error": "empty_transcript" }` for empty input.
- Builds extraction agent and task.
- Runs one-agent Crew (`Process.sequential`).
- Parses `crew.kickoff()` output as JSON and returns dict.
- On parse failure returns `{ "confidence": 0.0, "error": "crew_output_parse_failed" }`.

## Internal Components
### `_build_llm() -> LLM`
Creates CrewAI LLM client for Grok with:
- `model="xai/grok-3"`
- `base_url="https://api.x.ai/v1"`
- `api_key=os.environ["XAI_API_KEY"]`
- `temperature=0.1`

### `MedicalExtractionTool(BaseTool)`
CrewAI Tool that performs direct model extraction call.

Methods:
- `_get_client() -> OpenAI`: lazy OpenAI-compatible client creation.
- `_run(transcript: str) -> str`:
  - Loads prompt from disk every call.
  - Sends prompt as system message and transcript as user message.
  - Validates response as JSON.
  - Returns safe fallback JSON with `error="json_parse_failed"` on invalid output.

### `create_extraction_agent() -> Agent`
Builds Agent with:
- role: Medical Data Extraction Specialist
- Malayalam + HMIS/MCTS focused backstory
- tools: `[MedicalExtractionTool()]`
- `allow_delegation=False`, `verbose=True`

### `create_extraction_task(agent, transcript) -> Task`
Builds task that instructs the agent to use its tool and return JSON exactly.

## Prompt Source
Prompt is read at runtime from:
- [nirvaah/nirvaah-backend/data/extraction_prompt.txt](../nirvaah-backend/data/extraction_prompt.txt)

This allows iterative prompt updates without server restarts.

## Test Script
[tests/test_extraction.py](../nirvaah-backend/tests/test_extraction.py) includes 4 transcript scenarios:
1. Clear English
2. Mixed Malayalam-English
3. Malayalam numbers
4. Vague/incomplete (expects confidence < 0.5)

Run:
```bash
cd nirvaah/nirvaah-backend
python tests/test_extraction.py
```

## Environment Variables
Minimum required for Agent 1:
- `XAI_API_KEY`

## Notes / Current Limitations
- If the model returns fenced output or malformed JSON, code tries cleanup and falls back safely.
- Extraction quality depends on prompt quality and transcript clarity.
