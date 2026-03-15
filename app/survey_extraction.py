"""
app/survey_extraction.py
--------------------
Loads survey-specific Claude prompts and calls the Anthropic API.
Same pattern as existing extraction logic — just a different prompt file.
"""

import json
import os
import anthropic

PROMPT_FILES = {
    'leprosy':    'data/survey_prompt_leprosy.txt',
    'pulse_polio': 'data/survey_prompt_pulse_polio.txt',
    'above_30':   'data/survey_prompt_above_30.txt',
    'pregnant':   'data/survey_prompt_pregnant.txt',
}

def load_survey_prompt(survey_type: str) -> str:
    path = PROMPT_FILES.get(survey_type)
    if not path:
        raise ValueError(f"Unknown survey type: {survey_type}")
    
    # Path is relative to the project root
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    full_path = os.path.join(base_dir, path)
    
    with open(full_path, 'r', encoding='utf-8') as f:
        return f.read()

async def extract_survey_data(transcript: str, survey_type: str) -> dict:
    # Get API key
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("[SURVEY] WARNING: ANTHROPIC_API_KEY not set!")
        return {'survey_type': survey_type, 'confidence': 0.0, '_parse_error': "API Key missing"}

    client = anthropic.AsyncAnthropic(api_key=api_key)
    system_prompt = load_survey_prompt(survey_type)
    
    try:
        response = await client.messages.create(
            model='claude-3-5-sonnet-20241022',
            max_tokens=1000,
            temperature=0.1,
            system=system_prompt,
            messages=[{'role': 'user', 'content': transcript}],
        )
        text = response.content[0].text
        
        # Strip markdown fences if Claude returned them
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.lower().startswith("json"):
                text = text[4:]
        text = text.strip()
        
        return json.loads(text)
    except Exception as e:
        print(f"[SURVEY] Extraction failed: {e}")
        return {'survey_type': survey_type, 'confidence': 0.0, '_parse_error': str(e)}
