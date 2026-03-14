# Agent 2: Validation Agent

## File Map
- Agent implementation: [validation.py](../nirvaah-backend/app/validation.py)
- Validation rules: [validation_rules.py](../nirvaah-backend/data/validation_rules.py)
- Pipeline state: [state.py](../nirvaah-backend/app/state.py)
- Tests: [test_validation.py](../nirvaah-backend/tests/test_validation.py)

## Purpose
Validates extracted medical fields against hard range rules and confidence thresholds, sets clinical alert flags, and triggers the clarification flow if anything is too uncertain or physiologically impossible.

## Runtime Stack
- **Validation logic**: Pure Python (no AI)
- **Clarification messages**: Groq (`llama-3.3-70b-versatile`) for bilingual WhatsApp replies
- **Secrets**: `GROQ_API_KEY`, `CLARIFICATION_CONFIDENCE_THRESHOLD` (default `0.70`)

## Public API

### `run_range_checks(extracted: dict) -> tuple[dict, list, list]`
Checks every field against `VALIDATION_RULES`. Returns:
1. **cleaned dict** — impossible values replaced with `None`
2. **alerts** — clinical alert strings (e.g. `"pre_eclampsia_risk"`)
3. **clarification_fields** — fields needing re-entry

### `check_confidence(extracted: dict) -> tuple[bool, str]`
Checks overall + field-level confidence against threshold. Returns `(needs_clarification, problem_field)`.

### `generate_clarification_message(field, extracted) -> str`
Uses Groq to generate a bilingual (English + Malayalam) WhatsApp clarification message. Falls back to hardcoded message on API failure.

### `validate_fields(extracted: dict) -> dict`
Core function tying range checks + confidence together. Raises `ClarificationRequired` if invalid, otherwise returns cleaned dict with `validation_alerts`.

### `validation_node(state: PipelineState) -> dict`
LangGraph node. Returns state updates: `validated_fields`, `validation_alerts`, `clarification_needed`, `clarification_question`, `errors`.

## Validation Rules

| Field | Range | Alert Low | Alert High | Special |
|---|---|---|---|---|
| `bp_systolic` | 70–180 mmHg | < 90 (shock) | > 140 (hypertension) | |
| `bp_diastolic` | 40–120 mmHg | | > 90 | + systolic > 140 → pre-eclampsia |
| `hemoglobin` | 5.0–18.0 g/dL | < 11.0 (anemia) | | < 7.0 → severe anemia |
| `weight_kg` | 30–150 kg | | | |
| `iron_tablets_given` | 0–100 | | | |
| `gestational_age_weeks` | 4–42 | | > 42 (overdue) | |
| `baby_weight_kg` | 0.5–6.0 kg | < 2.5 (low birth weight) | | |

## Clinical Alerts Generated
`bp_systolic_high_alert`, `bp_systolic_low_alert`, `bp_diastolic_high_alert`, `pre_eclampsia_risk`, `hemoglobin_low_alert`, `severe_anemia_critical`, `baby_weight_kg_low_alert`, `gestational_age_weeks_high_alert`, `*_impossible_value`

## Tests
```bash
cd nirvaah/nirvaah-backend
python tests/test_validation.py
```
6 tests: normal ANC, impossible BP, high BP alerts, low confidence, severe anemia, full pipeline.
