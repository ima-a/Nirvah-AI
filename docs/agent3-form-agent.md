# Agent 3: Form Agent

## File Map
- Agent implementation: [form_agent.py](../nirvaah-backend/app/form_agent.py)
- Schema registry: [schema_registry.json](../nirvaah-backend/data/schema_registry.json)
- Pipeline state: [state.py](../nirvaah-backend/app/state.py)
- Tests: [test_form_agent.py](../nirvaah-backend/tests/test_form_agent.py)

## Purpose
Maps validated medical fields to three government database schemas (HMIS, MCTS, Kerala HIMS) using a JSON schema registry. Uses Groq only for derived field fallback and unmapped field suggestions.

## Runtime Stack
- **Core mapping**: Pure Python (no AI)
- **Derived fields**: Pure Python rules for known derivations, Groq fallback for unknown
- **Unmapped fields**: Groq suggests destination field names
- **Schema source**: `data/schema_registry.json`

## Public API

### `map_to_forms(validated: dict) -> dict`
Main function. Returns `{"hmis": {...}, "mcts": {...}, "kerala_hims": {...}}` with `_visit_type` and `_destination` metadata.

### `map_to_schema(validated, schema) -> dict`
Maps validated fields to one destination schema dict. Handles direct, null (skip), and derived mappings.

### `compute_derived_field(field_name, source_fields, validated) -> any`
Computes derived fields from validated data.

### `handle_unmapped_fields(validated, mapped, destination) -> dict`
Uses Groq to suggest destination field names for extracted fields not in the registry.

### `form_agent_node(state: PipelineState) -> dict`
LangGraph node. Sets `mapped_forms` and `errors`.

## Schema Registry Structure
Top-level keys = visit types. Each has `hmis_fields`, `mcts_fields`, `kerala_hims_fields`.

| Visit Type | HMIS Fields | MCTS Fields | Kerala HIMS Fields |
|---|---|---|---|
| `anc_visit` | 13 | 9 | 7 |
| `pnc_visit` | 5 | 5 | 3 |
| `immunisation_visit` | 3 | 4 | 2 |
| `family_planning_visit` | 2 | 2 | 1 |

## Derived Fields (Pure Python)

| Destination Field | Source | Logic |
|---|---|---|
| `hb_status` | hemoglobin | ≥11→normal, ≥7→low, <7→critically_low |
| `anemia_grade` | hemoglobin | ≥11→none, ≥10→mild, ≥7→moderate, <7→severe |
| `bp_category` | systolic+diastolic | ≥140/90→hypertensive, ≥130/80→elevated, else normal |
| `baby_weight_category` | baby_weight_kg | ≥2.5→normal, <2.5→low_birth_weight |

## Tests
```bash
cd nirvaah/nirvaah-backend
python tests/test_form_agent.py
```
6 tests: HMIS mapping, MCTS mapping, Kerala HIMS derived fields, metadata, unknown visit type, full pipeline.
