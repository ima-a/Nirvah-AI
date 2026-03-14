# pipeline.py — orchestrates all 11 stages via LangGraph
# This stub is replaced by the AI Teammate's full implementation

async def run_pipeline(sender_phone: str, audio_bytes: bytes = None,
                       image_bytes: bytes = None, text: str = None):
    """
    Entry point for all message processing.
    Stub: just prints what was received so you can test Twilio.
    """
    print(f'[PIPELINE] Message from: {sender_phone}')
    if text:
        print(f'[PIPELINE] Text: {text}')
    if audio_bytes:
        print(f'[PIPELINE] Voice note: {len(audio_bytes)} bytes')
    if image_bytes:
        print(f'[PIPELINE] Image: {len(image_bytes)} bytes')
    # Stub response — real response comes from AI Teammate's pipeline
    return {'status': 'received', 'phone': sender_phone}
