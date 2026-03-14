"""
Agent 1 — Medical Data Extraction Agent
Receives a raw ASHA-worker transcript (Malayalam / English / mixed) and
returns a structured dict of medical fields via Groq (llama-3.3-70b-versatile).
"""

from dotenv import load_dotenv
load_dotenv()

import json
import os
from groq import Groq
from app.state import PipelineState

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

SYSTEM_PROMPT = """You are a medical data extraction system for Kerala ASHA workers.
Extract structured health data from voice transcripts in Malayalam, English, or mixed Malayalam-English.

Respond ONLY with valid JSON. No markdown fences. No explanation. No preamble. Just the JSON object.

OUTPUT SCHEMA:
{
  "visit_type": "anc_visit | pnc_visit | immunisation_visit | family_planning_visit",
  "beneficiary_name": null,
  "bp_systolic": null,
  "bp_diastolic": null,
  "hemoglobin": null,
  "weight_kg": null,
  "iron_tablets_given": null,
  "gestational_age_weeks": null,
  "anc_visit_number": null,
  "next_visit_date": null,
  "next_visit_location": null,
  "vaccines_given": [],
  "baby_weight_kg": null,
  "referred": false,
  "referral_location": null,
  "bpl_card": false,
  "clinical_notes": null,
  "overall_confidence": 0.0,
  "field_confidence": {
    "bp_systolic": 0.0,
    "hemoglobin": 0.0,
    "weight_kg": 0.0
  }
}

MALAYALAM TERM MAPPINGS:

-- Vitals --
ബിപി / ബി.പി / BP = bp_systolic + bp_diastolic
  "110 70" OR "110/70" OR "110, 70" -> systolic=110, diastolic=70
  ഹൈ ആണ് = elevated, still extract numbers
  നോർമലാണ് = normal, still extract numbers
ഹീമോഗ്ലോബിൻ / Hb = hemoglobin
  വെരി ലോ = low value, still extract the number
അയൺ ടാബ്ലേറ്റ്സ് / അയൺ ടാബ്ലെറ്റ്സ് / iron tablets / IFA = iron_tablets_given
വെയിറ്റ് / weight = weight_kg (mother) or baby_weight_kg (baby)

-- Locations --
CRITICAL: Always return locations in English only, never Malayalam script.
പിഎച്ച്സി / PHC / പി.എച്ച്.സി = ALWAYS return "PHC"
സിഎച്ച്സി / CHC / സി.എച്ച്.സി = ALWAYS return "CHC"
റിഫർഡ് ടു = referred=true + referral_location in English (PHC or CHC)

-- People --
ബേബി / baby = baby context, use baby_weight_kg
മദർ / mother = mother context, use weight_kg

-- Cards --
ബി.പി.എൽ കാർഡ് / BPL card = bpl_card=true

-- Vaccines --
vaccines_given is always an ARRAY. Add every vaccine mentioned.
ബിസിജി = "BCG"
ഒപിവിഒ = "OPV0"
വൈറ്റമിൻ എ = "VitaminA"
പെന്റാവേലന്റ് = "Pentavalent"
If multiple vaccines given, include all: ["BCG", "OPV0"]

-- Visit Types --
ഫസ്റ്റ് വിസിറ്റ് = anc_visit, anc_visit_number=1
വാക്സിൻ visit = immunisation_visit
പോസ്റ്റ്നേറ്റൽ = pnc_visit

MALAYALAM NUMBERS:
ഒന്ന്=1, രണ്ട്=2, മൂന്ന്=3, നാല്=4, അഞ്ച്=5
ആറ്=6, ഏഴ്=7, എട്ട്=8, ഒമ്പത്=9, പത്ത്=10
ഇരുപത്=20, മുപ്പത്=30, നാല്പത്=40, അമ്പത്=50
അറുപത്=60, എഴുപത്=70

ENGLISH NUMBERS IN MALAYALAM:
സിക്സ്ടി ടു=62, സെവൻ=7, നയൻ=9, ടെൻ=10
പോയിൻറ് / പോയിന്റ് = decimal point
പത്ത് പോയിൻറ് രണ്ട് = 10.2
മൂന്ന് പോയിന്റ് രണ്ട് = 3.2
സെവൻ പോയിൻട് ടു = 7.2

NEXT VISIT:
"14 ന്" = next_visit_date="14"
"പിഎച്ച്സിയിൽ വരണം" = next_visit_location="PHC"
"സിഎച്ച്സിയിൽ" = next_visit_location="CHC"

RULES:
1. Extract ONLY what is clearly stated. Never guess.
2. If field not mentioned set it to null.
3. Baby weight goes to baby_weight_kg. Mother weight goes to weight_kg.
4. If referred set referred=true and extract referral_location in English.
5. Set overall_confidence to 0.95 if all key fields are clear.
6. vaccines_given is always an array, even if only one vaccine.
7. Location fields (next_visit_location, referral_location) must always be English: PHC or CHC.
8. Return pure JSON only, nothing else.
"""


def extract_fields(transcript: str) -> dict:
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": f"Extract fields from this transcript:\n\n{transcript}"}
            ],
            temperature=0.1,
            max_tokens=1000,
        )

        raw = response.choices[0].message.content.strip()

        # Strip markdown fences if model adds them
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        return json.loads(raw)

    except json.JSONDecodeError as e:
        return {"overall_confidence": 0.0, "error": f"JSON parse failed: {str(e)}"}
    except Exception as e:
        return {"overall_confidence": 0.0, "error": str(e)}


async def extract_fields_async(transcript: str) -> dict:
    return extract_fields(transcript)


async def process_input(
    audio_bytes: bytes = None,
    text: str = None,
    image_bytes: bytes = None
) -> dict:
    """
    Routes incoming input to the appropriate processing path:
      - voice (audio_bytes) → ElevenLabs STT → extract_fields
      - text → extract_fields directly
      - image (image_bytes) → OCR → extract_fields
    
    Returns the extraction result dict with added input_source and
    ocr_text fields for pipeline state.
    """
    result = {}
    
    if audio_bytes:
        # Voice path — transcribe with ElevenLabs then extract
        try:
            from app.transcription import transcribe_audio
            transcript = await transcribe_audio(audio_bytes)
        except Exception as e:
            print(f"[EXTRACTION] Transcription failed: {e}")
            transcript = ""
        result = extract_fields(transcript) if transcript else {"overall_confidence": 0.0, "error": "transcription_failed"}
        result["input_source"] = "voice"
        result["ocr_text"] = ""
    
    elif image_bytes:
        # Image path — OCR then extract
        try:
            from app.ocr import extract_text_from_image
            ocr_text = await extract_text_from_image(image_bytes)
        except Exception as e:
            print(f"[EXTRACTION] OCR failed: {e}")
            ocr_text = ""
        result = extract_fields(ocr_text) if ocr_text else {"overall_confidence": 0.0, "error": "ocr_failed"}
        result["input_source"] = "image"
        result["ocr_text"] = ocr_text or ""
    
    elif text:
        # Text path — extract directly
        result = extract_fields(text)
        result["input_source"] = "text"
        result["ocr_text"] = ""
    
    else:
        result = {"overall_confidence": 0.0, "error": "no_input"}
        result["input_source"] = "unknown"
        result["ocr_text"] = ""
    
    return result


def extraction_node(state: PipelineState) -> dict:
    """
    LangGraph node wrapper for Agent 1.
    
    This function is the bridge between LangGraph's state-passing system 
    and the existing extract_fields() function. LangGraph calls this with 
    the full pipeline state. We read the transcript, run extraction, and 
    return only the keys we changed — LangGraph merges our return dict 
    back into the full state automatically.
    """
    import asyncio
    
    transcript = state.get("transcript", "")
    
    if not transcript:
        # No transcript means nothing to extract. 
        # Append to errors list rather than overwriting it.
        return {
            "extracted_fields": {},
            "errors": state.get("errors", []) + ["extraction: empty transcript"],
            "clarification_needed": True,
            "clarification_question": "No message received. Please send your voice note or type your update."
        }
    
    # Call the existing extract_fields() function.
    # extract_fields_async is an async function, so we run it with asyncio.
    # In a FastAPI context this works because we are running inside an 
    # event loop — asyncio.run() would fail here, so we use a coroutine 
    # approach instead.
    try:
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(extract_fields_async(transcript))
    except RuntimeError:
        # If there is already a running event loop (FastAPI), use this instead
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, extract_fields_async(transcript))
            result = future.result()
    
    # Attach the input_source from state so downstream agents know 
    # where this data came from
    result["input_source"] = state.get("input_source", "unknown")
    
    # Check if confidence is too low to continue — if so, set the 
    # clarification flag so the conditional edge in pipeline.py routes
    # to the clarification node instead of the validation node
    overall_confidence = result.get("overall_confidence", 0.0)
    needs_clarification = overall_confidence < 0.70
    
    clarification_question = ""
    if needs_clarification:
        clarification_question = (
            "Some details in your message were unclear. "
            "Could you please repeat the key readings? "
            "For example: BP 110/70, Hemoglobin 10.2, Weight 62kg."
        )
    
    return {
        "extracted_fields": result,
        "clarification_needed": needs_clarification,
        "clarification_question": clarification_question,
        "errors": state.get("errors", [])  
        # Pass errors through unchanged — we had no errors in this node
    }
