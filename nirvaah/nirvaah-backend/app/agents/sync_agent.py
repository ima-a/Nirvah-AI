"""
app/agents/sync_agent.py — Agent 4: Sync Agent for Nirvaah AI.

Writes mapped form data to Supabase and Google Sheets using Celery
background tasks so the FastAPI response returns quickly within
Twilio's 15-second webhook timeout.

Also manages Redis-backed clarification state for pending worker replies.
"""

from dotenv import load_dotenv
load_dotenv()

import os
import json
import uuid
from datetime import datetime, timezone
from celery import Celery
from supabase import create_client, Client
from app.state import PipelineState

# ----------------------------------------------------------------
# SUPABASE CLIENT (lazy initialization)
# Uses service role key to bypass Row Level Security during
# background writes. Never expose the service role key to the frontend.
# Lazy-init so the module can be imported without env vars set.
# ----------------------------------------------------------------
_supabase_client: Client | None = None


def get_supabase() -> Client:
    global _supabase_client
    if _supabase_client is None:
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        if not url or not key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
        _supabase_client = create_client(url, key)
    return _supabase_client

# ----------------------------------------------------------------
# CELERY APP
# Uses Upstash Redis as the message broker and result backend.
# ----------------------------------------------------------------
celery_app = Celery(
    "nirvaah",
    broker=os.environ.get("REDIS_URL", ""),
    backend=os.environ.get("REDIS_URL", "")
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",        # IST — important for off-hours anomaly detection
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,            # acknowledge after completion, not on pickup
)

# ----------------------------------------------------------------
# REDIS CLARIFICATION HELPERS
# Uses upstash_redis (HTTP-based) for Upstash compatibility.
# Reads UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN from env.
# ----------------------------------------------------------------

try:
    from upstash_redis import Redis as UpstashRedis
    redis_client = UpstashRedis.from_env()
except Exception:
    # If Upstash Redis is not configured, use a no-op stub
    # so the module can still be imported for offline testing
    redis_client = None


def store_pending_clarification(phone: str, field: str, question: str):
    """
    Store a pending clarification request in Redis keyed by phone number.
    Expires after 1 hour — if the worker does not respond within an hour,
    the clarification is abandoned and they must start fresh.
    TTL of 3600 seconds prevents Redis from filling up with stale entries.
    """
    if redis_client is None:
        print("[SYNC] Redis not configured — skipping clarification store")
        return
    key = f"clarification:{phone}"
    value = json.dumps({
        "field": field,
        "question": question,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    redis_client.set(key, value, ex=3600)


def get_pending_clarification(phone: str) -> dict | None:
    """
    Retrieve a pending clarification for this phone number, if one exists.
    Returns None if no pending clarification (normal submission path).
    Returns the clarification dict if the worker is responding to a question.
    """
    if redis_client is None:
        return None
    key = f"clarification:{phone}"
    value = redis_client.get(key)
    if value is None:
        return None
    return json.loads(value)


def clear_pending_clarification(phone: str):
    """
    Delete the pending clarification after the worker has responded.
    Called by webhook.py after a clarification reply is successfully processed.
    """
    if redis_client is None:
        return
    key = f"clarification:{phone}"
    redis_client.delete(key)


# ----------------------------------------------------------------
# SUPABASE WRITE FUNCTION
# ----------------------------------------------------------------

def write_to_supabase(
    mapped_forms: dict,
    validated_fields: dict,
    sender_phone: str,
    input_source: str,
    record_id: str
) -> dict:
    """
    Writes the record to Supabase synchronously inside the Celery task.
    Writes to two tables: 'records' (main visit data) and 'beneficiaries'
    (individual beneficiary profiles).
    """
    try:
        # Table 1 — records (main visit data)
        record_row = {
            "id": record_id,
            "worker_phone": sender_phone,
            "visit_type": validated_fields.get("visit_type"),
            "beneficiary_name": validated_fields.get("beneficiary_name"),
            "input_source": input_source,
            "extracted_data": validated_fields,
            "hmis_mapped": mapped_forms.get("hmis", {}),
            "mcts_mapped": mapped_forms.get("mcts", {}),
            "kerala_hims_mapped": mapped_forms.get("kerala_hims", {}),
            "sync_status": "synced",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        get_supabase().table("records").insert(record_row).execute()

        # Table 2 — beneficiaries (upsert individual profiles)
        beneficiary_name = validated_fields.get("beneficiary_name")
        if beneficiary_name:
            beneficiary_row = {
                "beneficiary_name": beneficiary_name,
                "worker_phone": sender_phone,
                "last_visit_date": datetime.now(timezone.utc).isoformat(),
                "last_visit_type": validated_fields.get("visit_type"),
                "last_hemoglobin": validated_fields.get("hemoglobin"),
                "last_bp_systolic": validated_fields.get("bp_systolic"),
                "last_weight_kg": validated_fields.get("weight_kg"),
                "next_visit_date": validated_fields.get("next_visit_date"),
                "next_visit_location": validated_fields.get("next_visit_location")
            }
            get_supabase().table("beneficiaries").upsert(
                beneficiary_row,
                on_conflict="beneficiary_name,worker_phone"
            ).execute()

        return {"status": "success", "record_id": record_id}

    except Exception as e:
        return {"status": "failed", "error": str(e)}


# ----------------------------------------------------------------
# GOOGLE SHEETS WRITE FUNCTION
# ----------------------------------------------------------------

def write_to_google_sheets(
    mapped_forms: dict,
    validated_fields: dict,
    record_id: str
) -> dict:
    """
    Writes one row to the Google Sheet mock HMIS portal.
    Supplementary destination — failures here do NOT crash the pipeline
    since Supabase is the authoritative destination.
    """
    try:
        import gspread
        from google.oauth2.service_account import Credentials

        scopes = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = Credentials.from_service_account_file(
            os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", ""),
            scopes=scopes
        )
        gc = gspread.authorize(creds)
        sheet = gc.open_by_key(os.environ.get("GOOGLE_SHEETS_ID", ""))
        worksheet = sheet.get_worksheet(0)  # first sheet

        # Build row — HMIS mapped fields with timestamp and record ID
        row = [
            datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            record_id,
            validated_fields.get("visit_type", ""),
            validated_fields.get("beneficiary_name", ""),
            mapped_forms.get("hmis", {}).get("ANC_BP_SYS", ""),
            mapped_forms.get("hmis", {}).get("ANC_BP_DIA", ""),
            mapped_forms.get("hmis", {}).get("ANC_HB", ""),
            mapped_forms.get("hmis", {}).get("ANC_WT", ""),
            mapped_forms.get("hmis", {}).get("ANC_IFA", ""),
            mapped_forms.get("hmis", {}).get("ANC_NEXT_VISIT", ""),
            mapped_forms.get("hmis", {}).get("ANC_NEXT_LOC", ""),
        ]
        worksheet.append_row(row)

        return {"status": "success"}

    except Exception as e:
        return {"status": "failed", "error": str(e)}


# ----------------------------------------------------------------
# CELERY BACKGROUND TASK
# ----------------------------------------------------------------

@celery_app.task(
    bind=True,
    max_retries=3,
    name="nirvaah.sync_record"
)
def sync_record_task(
    self,
    mapped_forms: dict,
    validated_fields: dict,
    sender_phone: str,
    input_source: str,
    record_id: str
):
    """
    Celery background task that performs the actual database writes.

    Runs outside the FastAPI request cycle so the HTTP response can
    return to Twilio immediately. This task is picked up and executed
    by a separate Celery worker process.

    Retry strategy:
      - Supabase write: no retry. If it fails, record the error and stop.
      - Google Sheets write: retry up to 3 times with exponential backoff.
    """
    results = {}

    # Step 1 — Write to Supabase first (authoritative)
    supabase_result = write_to_supabase(
        mapped_forms, validated_fields, sender_phone, input_source, record_id
    )
    results["supabase"] = supabase_result

    # If Supabase failed, do not proceed to Google Sheets.
    if supabase_result["status"] == "failed":
        results["google_sheets"] = {
            "status": "skipped",
            "reason": "supabase_write_failed"
        }
        return results

    # Step 2 — Write to Google Sheets (supplementary, with retry)
    sheets_result = write_to_google_sheets(mapped_forms, validated_fields, record_id)
    results["google_sheets"] = sheets_result

    # Retry with exponential backoff: 5s, 10s, 20s
    if sheets_result["status"] == "failed":
        raise self.retry(
            countdown=5 * (2 ** self.request.retries),
            exc=Exception(sheets_result.get("error", "google_sheets_write_failed"))
        )

    results["record_id"] = record_id
    return results


# ----------------------------------------------------------------
# MAIN SYNC FUNCTION
# ----------------------------------------------------------------

async def sync_record(
    mapped_forms: dict,
    validated_fields: dict,
    sender_phone: str,
    input_source: str = "unknown"
) -> dict:
    """
    Queues the sync task on Celery and returns immediately.
    Does NOT wait for the task to complete.

    The record_id is generated here (before queuing) so that:
    1. We can return it immediately to the pipeline for audit chain use
    2. The record_id is consistent between Supabase and Google Sheets
    3. We can reference the record in notifications before it is written
    """
    record_id = str(uuid.uuid4())

    # Queue the task — this returns almost instantly
    sync_record_task.delay(
        mapped_forms=mapped_forms,
        validated_fields=validated_fields,
        sender_phone=sender_phone,
        input_source=input_source,
        record_id=record_id
    )

    # Return optimistic status — queued, not written yet
    return {
        "supabase": "queued",
        "google_sheets": "queued",
        "record_id": record_id
    }


# ----------------------------------------------------------------
# LANGGRAPH NODE
# ----------------------------------------------------------------

def sync_node(state: PipelineState) -> dict:
    """
    LangGraph node for Agent 4 — Sync Agent.

    Reads mapped_forms from state, queues the Celery background task
    for database writes, and returns the sync_status immediately.
    The pipeline continues to Agent 5 without waiting for writes to complete.
    """
    import asyncio

    mapped_forms = state.get("mapped_forms", {})
    validated_fields = state.get("validated_fields", {})
    sender_phone = state.get("sender_phone", "")
    input_source = state.get("input_source", "unknown")

    if not mapped_forms or not any(mapped_forms.values()):
        return {
            "sync_status": {"supabase": "skipped", "google_sheets": "skipped"},
            "errors": state.get("errors", []) + ["sync: no mapped forms to sync"]
        }

    try:
        # Run the async sync_record function
        try:
            loop = asyncio.get_event_loop()
            sync_status = loop.run_until_complete(
                sync_record(mapped_forms, validated_fields, sender_phone, input_source)
            )
        except RuntimeError:
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(
                    asyncio.run,
                    sync_record(mapped_forms, validated_fields, sender_phone, input_source)
                )
                sync_status = future.result()

        return {
            "sync_status": sync_status,
            "errors": state.get("errors", [])
        }

    except Exception as e:
        return {
            "sync_status": {"supabase": "failed", "google_sheets": "failed"},
            "errors": state.get("errors", []) + [f"sync: {str(e)}"]
        }
