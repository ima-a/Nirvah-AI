# Agent 1: Medical Data Extraction Agent

## File Map
- Agent implementation: [extraction.py](../nirvaah-backend/app/agents/extraction.py)
- System prompt (inline): same file, `SYSTEM_PROMPT` constant
- External prompt (file-based): [extraction_prompt.txt](../nirvaah-backend/data/extraction_prompt.txt)
- Pipeline state: [state.py](../nirvaah-backend/app/state.py)
- Tests: [test_extraction.py](../nirvaah-backend/tests/test_extraction.py)

## Purpose
Receives a raw ASHA-worker transcript (Malayalam / English / mixed) and returns a structured dict of medical fields via Groq LLM (`llama-3.3-70b-versatile`).

## Runtime Stack
- **LLM**: Groq (`llama-3.3-70b-versatile`) via `groq` Python SDK
- **Temperature**: `0.1` (near-deterministic extraction)
- **Secrets**: `GROQ_API_KEY` from `.env`

## Public API

### `extract_fields(transcript: str) -> dict`
Synchronous extraction. Sends transcript to Groq with `SYSTEM_PROMPT`, parses JSON response. Returns structured dict or `{"overall_confidence": 0.0, "error": "..."}` on failure.

### `extract_fields_async(transcript: str) -> dict`
Async wrapper — calls `extract_fields()` directly.

### `process_input(audio_bytes, text, image_bytes) -> dict`
Routes incoming input to the appropriate processing path:
- **voice** (`audio_bytes`) → `transcribe_audio()` (ElevenLabs) → `extract_fields()`
- **text** → `extract_fields()` directly
- **image** (`image_bytes`) → `extract_text_from_image()` (OCR) → `extract_fields()`

Returns the extraction result dict with `input_source` and `ocr_text` fields added.

### `extraction_node(state: PipelineState) -> dict`
LangGraph node wrapper. Reads `state["transcript"]`, runs extraction, checks confidence (`< 0.70` triggers clarification), and returns state updates:
- `extracted_fields` — the structured dict
- `clarification_needed` — bool
- `clarification_question` — WhatsApp message if needed
- `errors` — accumulated error list

## Output Schema
```json
{
  "visit_type": "anc_visit | pnc_visit | immunisation_visit | family_planning_visit",
  "beneficiary_name": "string | null",
  "bp_systolic": "int | null",
  "bp_diastolic": "int | null",
  "hemoglobin": "float | null",
  "weight_kg": "float | null",
  "iron_tablets_given": "int | null",
  "gestational_age_weeks": "int | null",
  "vaccines_given": ["array"],
  "baby_weight_kg": "float | null",
  "referred": "bool",
  "referral_location": "string | null",
  "bpl_card": "bool",
  "overall_confidence": "float 0.0-1.0",
  "field_confidence": {"field_name": "float 0.0-1.0"}
}
```

## Malayalam Support
Full term mappings for vitals, locations, vaccines, visit types, and number words (e.g. `മുപ്പത്` → 30, `പത്ത് പോയിൻറ് രണ്ട്` → 10.2).

## Tests
8 transcript scenarios in `test_extraction.py` covering English, mixed Malayalam-English, Malayalam numbers, referrals, vaccines, and anemia cases.

```bash
cd nirvaah/nirvaah-backend
python tests/test_extraction.py
```

## Environment Variables
| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | Yes | Groq API key for LLM calls |
