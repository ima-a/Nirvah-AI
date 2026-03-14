from fastapi import APIRouter, Form, Request
from app.pipeline import run_pipeline
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
        await run_pipeline(sender_phone, text=Body)

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
