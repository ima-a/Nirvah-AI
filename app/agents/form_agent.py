"""
app/form_agent.py — Agent 3: Form Agent for Nirvaah AI.

Maps validated medical fields to three government database schemas
(HMIS, MCTS, Kerala HIMS) using a schema registry. Uses Groq only
for derived field computation fallback and unmapped field handling.
All core mapping is pure Python.
"""

from dotenv import load_dotenv
load_dotenv()

import os
import json
from pathlib import Path
from groq import Groq
from app.state import PipelineState

groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# Load schema registry once at module startup
# BASE_DIR is the project root (3 levels up from this file: app/agents/form_agent.py -> agents -> app -> root)
BASE_DIR = Path(__file__).resolve().parent.parent.parent
REGISTRY_PATH = BASE_DIR / "data" / "schema_registry.json"


def load_registry() -> dict:
    with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


SCHEMA_REGISTRY = load_registry()


# ----------------------------------------------------------------
# DERIVED FIELD COMPUTATION
# ----------------------------------------------------------------

def compute_derived_field(
    field_name: str,
    source_fields: str,
    validated: dict
) -> any:
    """
    Handles fields whose registry value starts with "derived:".
    Uses pure Python rules for known derivations, falls back to
    Groq only for unknown ones.
    """

    # --- hb_status: derived from hemoglobin ---
    if source_fields == "derived:hemoglobin" and field_name == "hb_status":
        hb = validated.get("hemoglobin")
        if hb is None:
            return None
        try:
            hb = float(hb)
        except (TypeError, ValueError):
            return None
        if hb >= 11.0:
            return "normal"
        if hb >= 7.0:
            return "low"
        return "critically_low"

    # --- anemia_grade: derived from hemoglobin ---
    if source_fields == "derived:hemoglobin" and field_name == "anemia_grade":
        hb = validated.get("hemoglobin")
        if hb is None:
            return None
        try:
            hb = float(hb)
        except (TypeError, ValueError):
            return None
        if hb >= 11.0:
            return "none"
        if hb >= 10.0:
            return "mild"
        if hb >= 7.0:
            return "moderate"
        return "severe"

    # --- baby_weight_category: derived from baby_weight_kg ---
    if source_fields == "derived:baby_weight_kg" and field_name == "baby_weight_category":
        bw = validated.get("baby_weight_kg")
        if bw is None:
            return None
        try:
            bw = float(bw)
        except (TypeError, ValueError):
            return None
        if bw >= 2.5:
            return "normal"
        return "low_birth_weight"

    # --- bp_category: derived from bp_systolic + bp_diastolic ---
    if source_fields == "derived:bp_systolic+bp_diastolic" and field_name == "bp_category":
        sys_val = validated.get("bp_systolic")
        dia_val = validated.get("bp_diastolic")
        if sys_val is None or dia_val is None:
            return None
        try:
            sys_val = float(sys_val)
            dia_val = float(dia_val)
        except (TypeError, ValueError):
            return None
        if sys_val >= 140 or dia_val >= 90:
            return "hypertensive"
        if sys_val >= 130 or dia_val >= 80:
            return "elevated"
        return "normal"

    # --- Unknown derived field: fallback to Groq ---
    try:
        prompt = (
            f"Given a health record with these fields:\n"
            f"{json.dumps(validated, indent=2)}\n\n"
            f"Compute the value for '{field_name}' (derived from {source_fields}).\n"
            f"Respond with ONLY the computed value as a plain string. No explanation."
        )
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=100
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return None


# ----------------------------------------------------------------
# DIRECT FIELD MAPPER
# ----------------------------------------------------------------

def map_to_schema(validated: dict, schema: dict) -> dict:
    """
    Maps validated fields to a destination schema dict.
    Handles direct mappings, null (skip), and derived fields.
    """
    result = {}

    for destination_field, source in schema.items():
        try:
            if source is None:
                # No mapping defined for this field yet
                continue

            if isinstance(source, str) and source.startswith("derived:"):
                value = compute_derived_field(destination_field, source, validated)
                if value is not None:
                    result[destination_field] = value
            else:
                # Direct mapping
                value = validated.get(source)
                if value is not None:
                    result[destination_field] = value

        except (KeyError, TypeError):
            # Skip problematic field and continue
            continue

    return result


# ----------------------------------------------------------------
# UNMAPPED FIELDS HANDLER
# ----------------------------------------------------------------

def handle_unmapped_fields(
    validated: dict,
    mapped: dict,
    destination: str
) -> dict:
    """
    Handles fields in validated that didn't make it into mapped output.
    Asks Groq to suggest destination field names for unmapped data.
    """
    # Collect all source field names used in the registry for this destination
    visit_type = validated.get("visit_type", "anc_visit")
    if visit_type not in SCHEMA_REGISTRY:
        visit_type = "anc_visit"

    visit_schema = SCHEMA_REGISTRY.get(visit_type, {})
    fields_array = visit_schema.get("fields", [])

    # Build set of all source field names used
    all_source_fields = set()
    for entry in fields_array:
        fname = entry.get("field_name")
        if fname:
            all_source_fields.add(fname)

    # Fields to skip — metadata, not clinical data
    skip_fields = {
        "overall_confidence", "field_confidence", "input_source",
        "visit_type", "validation_alerts", "ocr_text"
    }

    unmapped = {
        k: v for k, v in validated.items()
        if k not in all_source_fields
        and v is not None
        and k not in skip_fields
    }

    if not unmapped:
        return mapped

    # Ask Groq where these fields should go
    try:
        prompt = (
            f"I am mapping Kerala ASHA health visit data to the {destination} system.\n"
            f"The following fields were extracted but have no defined mapping:\n"
            f"{json.dumps(unmapped, indent=2)}\n\n"
            f"For each field, suggest the most appropriate {destination} field name "
            f"to store it under. Respond ONLY with a valid JSON object mapping "
            f"extracted field name to destination field name.\n"
            f'Example: {{"clinical_notes": "REMARKS", "bpl_card": "BPL_STATUS"}}'
        )

        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=200
        )

        raw = response.choices[0].message.content.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        suggestions = json.loads(raw)

        for src_field, dest_field in suggestions.items():
            if src_field in unmapped:
                mapped[dest_field] = unmapped[src_field]

    except Exception:
        # On failure, just return mapped unchanged — no crash
        pass

    return mapped


# ----------------------------------------------------------------
# MAIN MAPPING FUNCTION
# ----------------------------------------------------------------

def build_destination_mappings(fields_array: list) -> tuple[dict, dict, dict]:
    """
    Build HMIS, MCTS, and Kerala HIMS mapping dicts from the fields array.
    Each entry in fields_array has: field_name, hmis_code, mcts_code, form_target.
    Returns three dicts: {dest_code: source_field_name}
    """
    hmis = {}
    mcts = {}
    kerala = {}

    for entry in fields_array:
        field_name = entry.get("field_name")
        if not field_name:
            continue

        targets = entry.get("form_target", [])
        hmis_code = entry.get("hmis_code")
        mcts_code = entry.get("mcts_code")

        if "HMIS" in targets and hmis_code:
            hmis[hmis_code] = field_name
        if "MCTS" in targets and mcts_code:
            mcts[mcts_code] = field_name
        if "Kerala_eHealth_HIMS" in targets and hmis_code:
            kerala[hmis_code] = field_name

    return hmis, mcts, kerala


def map_to_forms(validated: dict) -> dict:
    """
    Maps validated fields to all three destination schemas.
    Returns a dict with keys "hmis", "mcts", "kerala_hims".
    Each value is a properly formatted dict for that destination.
    """
    visit_type = validated.get("visit_type")

    # If visit_type is unknown or not in registry, default to anc_visit
    if not visit_type or visit_type not in SCHEMA_REGISTRY:
        visit_type = "anc_visit"

    visit_schema = SCHEMA_REGISTRY[visit_type]
    fields_array = visit_schema.get("fields", [])

    # Build the destination mappings from fields array
    hmis_schema, mcts_schema, kerala_schema = build_destination_mappings(fields_array)

    # Map to each destination using the built schemas
    hmis = map_to_schema(validated, hmis_schema)
    mcts = map_to_schema(validated, mcts_schema)
    kerala_hims = map_to_schema(validated, kerala_schema)

    # Handle any unmapped fields by asking Groq where they should go
    hmis = handle_unmapped_fields(validated, hmis, "HMIS")
    mcts = handle_unmapped_fields(validated, mcts, "MCTS")
    kerala_hims = handle_unmapped_fields(validated, kerala_hims, "Kerala_HIMS")

    # Add metadata to each mapped form so sync_agent knows what it is
    hmis["_visit_type"] = visit_type
    hmis["_destination"] = "HMIS"
    mcts["_visit_type"] = visit_type
    mcts["_destination"] = "MCTS"
    kerala_hims["_visit_type"] = visit_type
    kerala_hims["_destination"] = "Kerala_HIMS"

    return {
        "hmis": hmis,
        "mcts": mcts,
        "kerala_hims": kerala_hims
    }


# ----------------------------------------------------------------
# LANGGRAPH NODE
# ----------------------------------------------------------------

def form_agent_node(state: PipelineState) -> dict:
    """
    LangGraph node for Agent 3 — Form Agent.

    Reads validated_fields from state, maps them to all three
    government database schemas, and writes the result to mapped_forms.

    This node does NOT write to any database — that is Agent 4's job.
    It only translates field names and formats.
    """
    validated = state.get("validated_fields", {})

    if not validated:
        return {
            "mapped_forms": {"hmis": {}, "mcts": {}, "kerala_hims": {}},
            "errors": state.get("errors", []) + ["form_agent: no validated fields to map"]
        }

    try:
        mapped = map_to_forms(validated)
        return {
            "mapped_forms": mapped,
            "errors": state.get("errors", [])
        }

    except Exception as e:
        return {
            "mapped_forms": {"hmis": {}, "mcts": {}, "kerala_hims": {}},
            "errors": state.get("errors", []) + [f"form_agent: {str(e)}"]
        }
