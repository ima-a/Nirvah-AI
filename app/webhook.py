from fastapi import APIRouter, Form, Request
from app.pipeline import run_pipeline
from app.middleware import process_webhook_entry, handle_consent_logic
import httpx, os

router = APIRouter()

@router.post('/webhook')
async def twilio_webhook(
    request: Request,
    From: str = Form(...),
    Body: str = Form(default=''),
    MediaUrl0: str = Form(default=None),
    MediaContentType0: str = Form(default=None),
    NumMedia: str = Form(default='0')
):
    # Remove the 'whatsapp:' prefix to get the plain phone number
    sender_phone = From.replace('whatsapp:', '')
    print(f'[WEBHOOK] Message from: {sender_phone}')
    print(f'[WEBHOOK] NumMedia: {NumMedia}, Body: {Body}')

    # --- DPDP Act 2023 compliance: strip PII before anything enters the pipeline ---
    webhook_log = process_webhook_entry(Body, sender_phone)
    clean_body = webhook_log['body_text']

    # Handle STOP / RECORD consent commands before routing to pipeline
    if Body.strip().upper() in ('STOP', 'RECORD'):
        consent_action = handle_consent_logic(Body)
        if consent_action == 'CONSENT_WITHDRAWN':
            from app.database import supabase
            try:
                supabase.table('beneficiaries') \
                    .update({'citizen_tracker_opted_out': True}) \
                    .eq('phone', sender_phone) \
                    .execute()
            except Exception as e:
                print(f'[WEBHOOK] Consent update failed: {e}')
            from app.notifications import send_whatsapp
            send_whatsapp(sender_phone, 'You have been unsubscribed from health updates. Text START to re-subscribe.')
        elif consent_action == 'DATA_ACCESS_REQUEST':
            from app.notifications import send_whatsapp
            send_whatsapp(sender_phone, 'Your health record request has been received. Your records will be sent shortly.')
        return '<Response></Response>'

    if int(NumMedia) > 0 and MediaUrl0:
        if 'audio' in (MediaContentType0 or ''):
            print('[WEBHOOK] Detected: voice note')
            audio_bytes = await download_twilio_media(MediaUrl0)
            await run_pipeline(sender_phone, audio_bytes=audio_bytes)
        elif 'image' in (MediaContentType0 or ''):
            print('[WEBHOOK] Detected: image')
            image_bytes = await download_twilio_media(MediaUrl0)
            await run_pipeline(sender_phone, image_bytes=image_bytes)
    else:
        print('[WEBHOOK] Detected: text message')
        await run_pipeline(sender_phone, text=clean_body)

    # Twilio REQUIRES this exact response within 15 seconds
    return '<Response></Response>'

async def download_twilio_media(url: str) -> bytes:
    """Downloads a voice note or image from Twilio's servers.
    Twilio requires your Account SID + Auth Token to download media."""
    account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
    auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
    async with httpx.AsyncClient() as client:
        response = await client.get(url, auth=(account_sid, auth_token))
        print(f'[WEBHOOK] Downloaded: {len(response.content)} bytes')
        return response.content
