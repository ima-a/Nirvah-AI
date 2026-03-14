"""
app/validation.py — Agent 2: Validation Agent for Nirvaah AI.

Validates extracted medical fields against hard range rules and confidence
thresholds, sets clinical alert flags, and triggers the clarification flow
if anything is too uncertain or physiologically impossible.

Uses Groq only for generating bilingual clarification messages.
All validation logic is pure Python.
"""

from dotenv import load_dotenv
load_dotenv()

import os
from groq import Groq
from data.validation_rules import VALIDATION_RULES, REQUIRED_FIELDS_BY_VISIT_TYPE
from app.state import PipelineState

groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))


class ClarificationRequired(Exception):
    """
    Raised when extracted data is too uncertain or invalid to proceed.
    Carries the field name that triggered clarification and the
    WhatsApp question to send back to the ASHA worker.
    """
    def __init__(self, field: str, question: str):
        self.field = field
        self.question = question
        super().__init__(f"Clarification needed for field: {field}")


def run_range_checks(extracted: dict) -> tuple[dict, list, list]:
    """
    Validate every extracted field against VALIDATION_RULES.

    Returns:
        cleaned: dict with impossible values replaced with None
        alerts: list of clinical alert strings
        clarification_fields: list of field names needing clarification
    """
    cleaned = dict(extracted)  # shallow copy
    alerts = []
    clarification_fields = []

    for field, rule in VALIDATION_RULES.items():
        value = cleaned.get(field)

        if value is None:
            # Field not mentioned — fine for optional fields
            continue

        try:
            value = float(value)
        except (TypeError, ValueError):
            # Can't validate non-numeric value
            continue

        # Check if value is physiologically impossible
        if value < rule["min"] or value > rule["max"]:
            cleaned[field] = None
            clarification_fields.append(field)
            alerts.append(f"{field}_impossible_value")
            continue

        # Value is in valid range — check alert thresholds
        if "alert_low" in rule and value < rule["alert_low"]:
            alerts.append(f"{field}_low_alert")

        if "alert_high" in rule and value > rule["alert_high"]:
            alerts.append(f"{field}_high_alert")

        # Special case: pre-eclampsia risk
        if field == "bp_diastolic" and value > 90:
            bp_sys = cleaned.get("bp_systolic")
            if bp_sys is not None:
                try:
                    if float(bp_sys) > 140:
                        alerts.append("pre_eclampsia_risk")
                except (TypeError, ValueError):
                    pass

        # Special case: severe anemia
        if field == "hemoglobin" and value < 7.0:
            alerts.append("severe_anemia_critical")

    return cleaned, alerts, clarification_fields


def check_confidence(extracted: dict) -> tuple[bool, str]:
    """
    Check whether Groq was confident enough in its extraction.

    Returns:
        needs_clarification: True if confidence is too low
        problem_field: name of the field with low confidence, or "overall"
    """
    threshold = float(os.environ.get("CLARIFICATION_CONFIDENCE_THRESHOLD", "0.70"))

    if extracted.get("overall_confidence", 0) < threshold:
        return (True, "overall")

    # Check field-level confidence for required fields given the visit type
    visit_type = extracted.get("visit_type")
    if visit_type and visit_type in REQUIRED_FIELDS_BY_VISIT_TYPE:
        required = REQUIRED_FIELDS_BY_VISIT_TYPE[visit_type]
        field_conf = extracted.get("field_confidence", {})
        for field in required:
            if field in field_conf and field_conf[field] < 0.70:
                return (True, field)

    return (False, "")


def generate_clarification_message(field: str, extracted: dict) -> str:
    """
    Use Groq to generate a short, friendly, bilingual clarification
    message to send back to the ASHA worker via WhatsApp.

    This is the ONLY place in validation.py where we call Groq.
    """
    prompt = f"""
An ASHA worker sent a health visit report but the {field} reading was 
unclear or missing. Generate a SHORT WhatsApp reply asking them to 
confirm this specific value.

Rules:
- Maximum 2 sentences
- Write in both English and Malayalam (English first, then Malayalam)
- Be specific about what value you need
- Keep it friendly and simple
- Do not use medical jargon

Field needing clarification: {field}
Current extracted data: {extracted}
"""

    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=150
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        # Fallback to a hardcoded message if Groq fails
        # We cannot let a clarification API failure block the pipeline
        return (
            f"Your {field} reading was unclear — please reply with the correct value. "
            f"നിങ്ങളുടെ {field} വ്യക്തമായിരുന്നില്ല — ദയവായി ശരിയായ മൂല്യം മറുപടി അയക്കുക."
        )


def validate_fields(extracted: dict) -> dict:
    """
    Core validation function. Runs range checks and confidence checks.
    Raises ClarificationRequired if data is too uncertain or impossible.
    Returns the validated dict with validation_alerts attached.

    Does NOT interact with LangGraph state — that is handled by
    validation_node(). This separation makes it easy to unit test.
    """
    # Step 1: Run range checks
    cleaned, alerts, clarification_fields = run_range_checks(extracted)

    # Step 2: Check confidence thresholds
    needs_conf_clarification, problem_field = check_confidence(cleaned)

    # Step 3: Determine if clarification is needed overall
    needs_clarification = len(clarification_fields) > 0 or needs_conf_clarification

    # Step 4: If clarification needed, generate message and raise
    if needs_clarification:
        problem = clarification_fields[0] if clarification_fields else problem_field
        question = generate_clarification_message(problem, cleaned)
        raise ClarificationRequired(field=problem, question=question)

    # Step 5: No issues — attach alerts and return
    cleaned["validation_alerts"] = alerts
    return cleaned


def validation_node(state: PipelineState) -> dict:
    """
    LangGraph node for Agent 2 — Validation Agent.

    Reads extracted_fields from state, runs all validation checks,
    and returns the appropriate state updates. If clarification is
    needed, sets clarification_needed=True so the conditional edge
    in pipeline.py routes to the clarification node.
    """
    extracted = state.get("extracted_fields", {})

    if not extracted:
        return {
            "validated_fields": {},
            "validation_alerts": [],
            "clarification_needed": True,
            "clarification_question": "No data was extracted from your message. Please try again.",
            "errors": state.get("errors", []) + ["validation: no extracted fields to validate"]
        }

    try:
        validated = validate_fields(extracted)
        alerts = validated.pop("validation_alerts", [])

        return {
            "validated_fields": validated,
            "validation_alerts": alerts,
            "clarification_needed": False,
            "clarification_question": "",
            "errors": state.get("errors", [])
        }

    except ClarificationRequired as e:
        # The pipeline will stop here and send a WhatsApp message
        # back to the ASHA worker asking for clarification.
        return {
            "validated_fields": extracted,  # pass through what we have
            "validation_alerts": [],
            "clarification_needed": True,
            "clarification_question": e.question,
            "errors": state.get("errors", [])
        }

    except Exception as e:
        # Unexpected error — log it but do not crash the pipeline.
        # Pass through the extracted fields unchanged.
        return {
            "validated_fields": extracted,
            "validation_alerts": [],
            "clarification_needed": False,
            "clarification_question": "",
            "errors": state.get("errors", []) + [f"validation: unexpected error: {str(e)}"]
        }
