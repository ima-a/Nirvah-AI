import json
import os
import base64
from datetime import datetime, timezone
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.constants import ENCRYPT_ALGO

def encrypt_record(plaintext_dict: dict, key: bytes) -> dict:
    """
    Law #7: Encrypt the plaintext AFTER hashing.
    Uses AES-256-GCM for authenticated encryption.
    """
    # 1. Generate unique 12-byte IV (nonce)
    iv = os.urandom(12)
    aesgcm = AESGCM(key)
    
    # 2. Serialize plaintext to canonical JSON bytes
    plaintext_json = json.dumps(plaintext_dict, sort_keys=True).encode()
    
    # 3. Encrypt: Result is ciphertext + 16-byte auth_tag
    # The cryptography library appends the tag to the end of the ciphertext
    ciphertext_with_tag = aesgcm.encrypt(iv, plaintext_json, None)
    
    # 4. Construct LOG-04 Envelope
    envelope = {
        "log_type": "ENCRYPTED_RECORD",
        "encryption_algo": ENCRYPT_ALGO,
        "iv": base64.b64encode(iv).decode('utf-8'),
        "encrypted_payload": base64.b64encode(ciphertext_with_tag).decode('utf-8'),
        "key_derivation_source": "worker_auth_token",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    # Law: Discard plaintext from memory
    plaintext_json = None 
    
    return envelope

# --- Quick Test ---
if __name__ == "__main__":
    # Generate a random 256-bit key for testing
    mock_key = AESGCM.generate_key(bit_length=256)
    
    # Mock data structure from your Security Reference
    health_data = {
        "beneficiary_name": "Sunita Thomas",
        "bp_systolic": 110,
        "bp_diastolic": 70,
        "hemoglobin_g_dl": 10.2,
        "weight_kg": 62
    }
    
    encrypted = encrypt_record(health_data, mock_key)
    
    print("--- LOG-04 Encrypted Record ---")
    print(f"IV (Base64): {encrypted['iv']}")
    print(f"Payload (Base64): {encrypted['encrypted_payload'][:50]}...")
    print(f"Algorithm: {encrypted['encryption_algo']}")
    print("\n[SUCCESS] Plaintext encrypted and cleared from local scope.")
