
import os
import secrets
from kyber_py.kyber import Kyber1024
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from Crypto.Protocol.KDF import HKDF
from Crypto.Hash import SHA256

class KyberManager:
    """
    Manages Post-Quantum Cryptography using Kyber-1024 (ML-KEM).
    """
    def __init__(self):
        # Generate Server Static Keypair on startup (or per session)
        self.pk, self.sk = Kyber1024.keygen()
        self.sessions = {} # Token -> Shared Secret

    def get_public_key(self):
        """Return the server's public key (to be sent to client)."""
        return self.pk

    def decapsulate_secret(self, ciphertext):
        """
        Recover the shared secret from the client's encapsulation.
        Returns: (shared_secret, session_token)
        """
        try:
            # Kyber Decapsulation
            # Correct Usage: decaps(sk, ciphertext)
            shared_secret = Kyber1024.decaps(self.sk, ciphertext)
            
            # Create a session token to reference this secret
            token = secrets.token_hex(16)
            self.sessions[token] = shared_secret
            
            return shared_secret, token
        except Exception as e:
            print(f"PQC Error: {e}")
            return None, None

    def encrypt_data(self, session_token, data):
        """
        Encrypt data using AES-GCM with the Kyber-derived shared secret.
        """
        if session_token not in self.sessions:
            raise ValueError("Invalid Session Token")
            
        shared_secret = self.sessions[session_token]
        
        # Derive a strong AES-256 key from the Kyber shared secret
        aes_key = HKDF(shared_secret, salt=None, key_len=32, hashmod=SHA256)
        
        # AES-GCM Encryption
        nonce = get_random_bytes(12)
        cipher = AES.new(aes_key, AES.MODE_GCM, nonce=nonce)
        ciphertext, tag = cipher.encrypt_and_digest(data)
        
        return nonce + tag + ciphertext

# Singleton instance
pqc_manager = KyberManager()
