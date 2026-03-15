from dotenv import load_dotenv
load_dotenv()

import httpx
import asyncio
import os

API_KEY = os.environ.get("ELEVENLABS_API_KEY")

async def transcribe_audio(audio_bytes: bytes) -> str:
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            "https://api.elevenlabs.io/v1/speech-to-text",
            headers={"xi-api-key": API_KEY},
            files={"file": ("note.m4a", audio_bytes, "audio/mp4")},
            data={"model_id": "scribe_v1", "language_code": "ml"}
        )
        return r.json().get("text", "")


# Test runner — only runs when called directly
async def main():
    for i in range(1, 6):
        with open(f"voice_note_{i}.m4a", "rb") as f:
            audio = f.read()
        transcript = await transcribe_audio(audio)
        print(f"\nNote {i}: {transcript}")

if __name__ == "__main__":
    asyncio.run(main())
