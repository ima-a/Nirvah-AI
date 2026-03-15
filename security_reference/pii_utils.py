import re
import hashlib
from constants import HASH_PREFIX

# Patterns for Indian PII based on Security Reference
# Aadhaar: 12 digits starting with 2-9 [cite: 859]
# Phone: 10 digits starting with 6-9 [cite: 860]
PII_PATTERNS = [
    (r'\b[2-9][0-9]{11}\b', '[AADHAAR_REDACTED]'),
    (r'\b[6-9][0-9]{9}\b', '[PHONE_REDACTED]')
]

def hash_identifier(value: str) -> str:
    """
    Law #2 & #4: Hash every identifier and add prefix.
    Required for sender_hash, worker_id_hash, and beneficiary_id_hash.
    """
    if not value:
        return None
    # Clean string, encode, and hash
    clean_value = str(value).strip().lower()
    hash_obj = hashlib.sha256(clean_value.encode())
    return f"{HASH_PREFIX}{hash_obj.hexdigest()}"

def strip_pii(text: str) -> str:
    """
    Redact PII from text before it enters the pipeline or any log. [cite: 864]
    Crucial for LOG-01 Webhook Raw processing.
    """
    if not text:
        return text
    for pattern, replacement in PII_PATTERNS:
        text = re.sub(pattern, replacement, text)
    return text

# --- Test the Logic ---
if __name__ == "__main__":
    # Test Law #2 & #4
    test_phone = "+919876543210"
    print(f"Hashed Identifier: {hash_identifier(test_phone)}")
    
    # Test PII Redaction for LOG-01
    test_text = "The ASHA worker reported that beneficiary 212345678901 called from 9876543210."
    print(f"Original Text: {test_text}")
    print(f"Stripped Text: {strip_pii(test_text)}")
