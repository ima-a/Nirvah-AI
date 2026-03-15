"""
app/sos.py — Secret SOS Emergency Alert System for Nirvaah AI.

ASHA workers in rural India sometimes face dangerous situations during
home visits. This module lets them send a secret code word (e.g. "jalebi")
via WhatsApp to silently trigger emergency alerts to:
  1. Supervisor
  2. Nearby ASHA worker
  3. Local authority

The response is SILENT — no confirmation is sent back to the worker,
so no one nearby sees a reply on their phone.

Uses a SEPARATE Twilio bot (different SID/token) so the SOS alerts
come from a different number than the normal health bot.
"""

import os
from datetime import datetime, timezone, timedelta
from twilio.rest import Client


# ----------------------------------------------------------------
# CONFIGURATION
# ----------------------------------------------------------------

def get_sos_keyword() -> str:
    """Get the SOS keyword from environment. Default: 'jalebi'."""
    return os.environ.get("SOS_KEYWORD", "jalebi").strip().lower()


def get_emergency_contacts() -> list[dict]:
    """
    Get list of emergency contacts from environment variables.
    Each contact has a phone number and a role label.
    """
    contacts = []

    supervisor = os.environ.get("SOS_SUPERVISOR_PHONE")
    if supervisor:
        contacts.append({"phone": supervisor.strip(), "role": "Supervisor"})

    nearby_asha = os.environ.get("SOS_NEARBY_ASHA_PHONE")
    if nearby_asha:
        contacts.append({"phone": nearby_asha.strip(), "role": "Nearby ASHA Worker"})

    authority = os.environ.get("SOS_AUTHORITY_PHONE")
    if authority:
        contacts.append({"phone": authority.strip(), "role": "District Authority"})

    return contacts


# ----------------------------------------------------------------
# TWILIO CLIENT
# ----------------------------------------------------------------

def _get_main_twilio_client() -> Client:
    """Returns the main Twilio bot client."""
    sid = os.environ.get("TWILIO_ACCOUNT_SID")
    token = os.environ.get("TWILIO_AUTH_TOKEN")
    if not sid or not token:
        raise RuntimeError("Main Twilio credentials not configured")
    return Client(sid, token)


# ----------------------------------------------------------------
# KEYWORD DETECTION
# ----------------------------------------------------------------

def is_sos_trigger(body: str) -> bool:
    """
    Check if the incoming message is the SOS keyword.
    Exact match only (case-insensitive, whitespace-stripped).
    'jalebi' → True
    'JALEBI' → True
    '  jalebi  ' → True
    'hello jalebi' → False (must be exact, not substring)
    """
    if not body:
        return False
    keyword = get_sos_keyword()
    return body.strip().lower() == keyword


# ----------------------------------------------------------------
# ALERT MESSAGES
# ----------------------------------------------------------------

def build_sos_message(sender_phone: str) -> str:
    """Build the emergency WhatsApp message text."""
    # IST timestamp
    ist_offset = timedelta(hours=5, minutes=30)
    ist_now = datetime.now(timezone.utc) + ist_offset
    timestamp = ist_now.strftime("%d %b %Y, %I:%M %p IST")

    return (
        f"🚨 *EMERGENCY SOS — Nirvaah AI* 🚨\n\n"
        f"An ASHA worker has triggered a distress signal.\n\n"
        f"📱 Worker phone: {sender_phone}\n"
        f"🕐 Time: {timestamp}\n\n"
        f"⚠️ *Immediate assistance may be needed.*\n"
        f"Please try to contact the worker or dispatch help to their last known location."
    )


# ----------------------------------------------------------------
# SEND ALERTS
# ----------------------------------------------------------------

async def handle_sos(sender_phone: str):
    """
    Main SOS handler. Called from webhook.py when keyword detected.

    - WhatsApp messages sent via the MAIN Twilio Whatsapp Bot
    - Voice calls sent via the MAIN Twilio Phone Number (just rings, no speech)

    Does NOT send any response back to the worker (silent).
    """
    print(f"[SOS] 🚨 EMERGENCY triggered by {sender_phone}")

    contacts = get_emergency_contacts()
    if not contacts:
        print("[SOS] WARNING: No emergency contacts configured!")
        return

    message_text = build_sos_message(sender_phone)

    main_client = None
    try:
        main_client = _get_main_twilio_client()
    except Exception as e:
        print(f"[SOS] ❌ Twilio client error: {e}")
        return

    # --- WhatsApp alerts ---
    sandbox_number = os.environ.get("TWILIO_SANDBOX_NUMBER", "")
    for contact in contacts:
        phone = contact["phone"]
        role = contact["role"]
        try:
            if sandbox_number:
                main_client.messages.create(
                    from_=sandbox_number,
                    to=f"whatsapp:{phone}",
                    body=message_text
                )
                print(f"[SOS] ✅ WhatsApp sent to {role} ({phone})")
        except Exception as e:
            print(f"[SOS] ❌ WhatsApp to {role} failed: {e}")

    # --- Voice calls (just ring, no speech needed) ---
    # Voice calls use TWILIO_PHONE_NUMBER, NOT the WhatsApp Sandbox Number
    voice_number = os.environ.get("TWILIO_PHONE_NUMBER", "")
    if voice_number:
        for contact in contacts:
            phone = contact["phone"]
            role = contact["role"]
            try:
                # Minimal TwiML: just hold the line open so the phone rings
                main_client.calls.create(
                    from_=voice_number,
                    to=phone,
                    twiml='<Response><Pause length="30"/></Response>'
                )
                print(f"[SOS] ✅ Call placed to {role} ({phone})")
            except Exception as e:
                print(f"[SOS] ❌ Call to {role} failed: {e}")
    else:
        print("[SOS] ⚠️ No TWILIO_PHONE_NUMBER configured — skipping voice calls")

    # Log to Supabase for audit trail
    try:
        _log_sos_event(sender_phone, contacts)
    except Exception as e:
        print(f"[SOS] Audit log failed (non-critical): {e}")

    print(f"[SOS] Alert sequence complete for {sender_phone}")


def _log_sos_event(sender_phone: str, contacts: list):
    """Log the SOS event to Supabase alerts table for audit trail."""
    try:
        from app.agents.anomaly import get_supabase
        get_supabase().table("alerts").insert({
            "worker_phone": sender_phone,
            "flag_type": "SOS_EMERGENCY",
            "anomaly_score": 1.0,
            "severity": "critical",
            "dismissed": False,
            "created_at": datetime.now(timezone.utc).isoformat()
        }).execute()
    except Exception:
        pass  # Audit logging must never block the SOS response

