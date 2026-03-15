"""
survey_handler.py
-----------------
Manages survey session state in Upstash Redis and routes incoming
WhatsApp messages through the correct survey flow.

Session state stored in Redis, keyed by sender_phone:
    survey:state:<phone>  →  JSON:
        {
            "stage": "menu" | "awaiting_voice",
            "survey_type": null | "leprosy" | "pulse_polio" | "above_30" | "pregnant"
        }
Session TTL: 1800 seconds (30 minutes of inactivity)
"""

import json
import os
from upstash_redis import Redis
from app.transcription import transcribe_audio
from app.survey_extraction import extract_survey_data
from app.survey_validation import validate_survey
from app.survey_notifications import (
    build_survey_confirmation,
    build_worker_referral_alert,
    build_supervisor_referral_alert,
)
from app.notifications import send_whatsapp
from app.audit_chain import create_audit_entry
from app.database import supabase

# Read the URL directly, Upstash Redis python SDK expects REDIS_URL or REST_URL 
# to be passed, but the constructor can take url and token if it's the REST client.
# Since the codebase previously used celary with standard redis, we'll use standard upstash_redis.Redis
try:
    redis = Redis(url=os.environ.get('UPSTASH_REDIS_REST_URL', ''), token=os.environ.get('UPSTASH_REDIS_REST_TOKEN', ''))
except Exception as e:
    print(f"[SURVEY] Warning: Upstash Redis init failed: {e}")
    redis = None

SESSION_TTL = 1800

SURVEY_TYPES = {
    '1': 'leprosy',
    '2': 'pulse_polio',
    '3': 'above_30',
    '4': 'pregnant',
}

MENU_MESSAGE = """Welcome to Nirvaah AI Survey Mode 📋

Please reply with the number of the survey you want to conduct:

1️⃣  Leprosy Survey
2️⃣  Pulse Polio Survey
3️⃣  People Above 30 Years
4️⃣  Pregnant Ladies

Reply with 1, 2, 3, or 4.
Type CANCEL to exit."""

CONFIRM_MESSAGES = {
    'leprosy': (
        "You selected: *Leprosy Survey* ✅\n\n"
        "Please send a voice note summarising your findings for this household — "
        "number of people screened, anyone with rashes, pin-prick test results, "
        "and who needs PHC referral."
    ),
    'pulse_polio': (
        "You selected: *Pulse Polio Survey* ✅\n\n"
        "Please send a voice note — number of children under 5, whether they were "
        "vaccinated today, any guest children, any children with fever/vomiting/"
        "diarrhoea, and whether the house needs a follow-up."
    ),
    'above_30': (
        "You selected: *Above 30 Screening* ✅\n\n"
        "Please send a voice note — for each person screened include their name, "
        "age, BP reading, blood sugar value (fasting or random), and any other complaints."
    ),
    'pregnant': (
        "You selected: *Pregnant Ladies Survey* ✅\n\n"
        "Please send a voice note with the usual ANC details — name, BP, Hb, "
        "weight, IFA tablets, next visit date, and any concerns."
    ),
}

# ── Session helpers ──────────────────────────────────────────────────────────

def get_session(phone: str) -> dict | None:
    if not redis:
        return None
    try:
        raw = redis.get(f'survey:state:{phone}')
        return json.loads(raw) if raw else None
    except Exception:
        return None

def set_session(phone: str, data: dict):
    if not redis:
        return
    try:
        redis.set(f'survey:state:{phone}', json.dumps(data), ex=SESSION_TTL)
    except Exception:
        pass

def clear_session(phone: str):
    if not redis:
        return
    try:
        redis.delete(f'survey:state:{phone}')
    except Exception:
        pass

def is_in_survey_session(phone: str) -> bool:
    return get_session(phone) is not None

# ── Main router ──────────────────────────────────────────────────────────────

async def handle_survey_message(phone: str, text: str = None, audio_bytes: bytes = None):
    """
    Routes the message to the correct stage based on session state.
    Stage 1 — no session yet:         show menu
    Stage 2 — session stage=menu:     process menu selection
    Stage 3 — session stage=awaiting_voice: process voice note
    """
    # If redis isn't configured, we can't run stateful surveys
    if not redis:
        send_whatsapp(phone, "Survey mode is not available right now. Please notify your supervisor.")
        return

    session = get_session(phone)

    # CANCEL at any point
    if text and text.strip().upper() == 'CANCEL':
        clear_session(phone)
        send_whatsapp(phone, 'Survey cancelled. Send SURVEY anytime to start again.')
        return

    # Stage 1 — no session, SURVEY keyword received → show menu
    if session is None:
        set_session(phone, {'stage': 'menu', 'survey_type': None})
        send_whatsapp(phone, MENU_MESSAGE)
        return

    # Stage 2 — worker is choosing from the menu
    if session['stage'] == 'menu':
        choice = text.strip() if text else ''
        survey_type = SURVEY_TYPES.get(choice)

        if not survey_type:
            send_whatsapp(phone, 'Please reply with 1, 2, 3, or 4 to choose a survey type. Type CANCEL to exit.')
            return

        set_session(phone, {'stage': 'awaiting_voice', 'survey_type': survey_type})
        send_whatsapp(phone, CONFIRM_MESSAGES[survey_type])
        return

    # Stage 3 — worker has selected survey type, now sends voice note
    if session['stage'] == 'awaiting_voice':
        survey_type = session['survey_type']

        if not audio_bytes:
            send_whatsapp(phone, 'Please send a voice note with your survey findings. Type CANCEL to exit.')
            return

        send_whatsapp(phone, f"Processng {survey_type.replace('_', ' ').title()}...")

        # Transcribe
        transcript = await transcribe_audio(audio_bytes)

        # Extract using survey-specific Claude prompt
        extracted = await extract_survey_data(transcript, survey_type)

        # Validate and apply referral rules
        try:
            validated = validate_survey(extracted)
        except Exception as e:
            print(f"[SURVEY] Validation failed: {e}")
            send_whatsapp(phone, "Failed to analyze survey data. Please try again or type CANCEL.")
            return

        # Write to Supabase records table with survey_type column
        try:
            record = supabase.table('records').insert({
                'worker_id': phone,
                'visit_type': 'survey',
                'survey_type': survey_type,
                'extracted_fields': validated,
                'sync_status': 'pending',
            }).execute().data[0]
        except Exception as e:
            print(f"[SURVEY] Supabase insert failed: {e}")
            send_whatsapp(phone, "Failed to save survey record database error.")
            return

        # Audit chain
        try:
            create_audit_entry(record, worker_id=phone)
        except Exception as e:
            print(f"[SURVEY] Audit log failed: {e}")

        # Write referral alerts to alerts table
        for alert in validated.get('_referral_alerts', []):
            try:
                supabase.table('alerts').insert({
                    'worker_phone': phone, # Schema mismatch protection vs prompt: using worker_phone
                    'flag_type': alert['flag_type'],
                    'severity': alert['severity'],
                    'flag_reason': alert['flag_reason'],
                    'dismissed': False,
                }).execute()
            except Exception as e:
                print(f"[SURVEY] Alert insert failed: {e}")

        # Send worker confirmation
        send_whatsapp(phone, build_survey_confirmation(validated, survey_type))

        # Send referral alert to worker if needed
        worker_alert = build_worker_referral_alert(validated, survey_type)
        if worker_alert:
            send_whatsapp(phone, worker_alert)

        # Send referral alert to supervisor if needed
        supervisor_alert = build_supervisor_referral_alert(validated, survey_type, worker_name=phone)
        if supervisor_alert:
            try:
                supervisor = supabase.table('workers').select('phone').eq('role', 'supervisor').limit(1).execute()
                if supervisor.data:
                    send_whatsapp(supervisor.data[0]['phone'], supervisor_alert)
            except Exception as e:
                print(f"[SURVEY] Failed to alert supervisor: {e}")

        # Clear session — one survey per session
        clear_session(phone)
        return
