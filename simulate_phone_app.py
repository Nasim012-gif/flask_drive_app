
import os
import requests
import argparse
from kyber_py.kyber import Kyber1024
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import HKDF
from Crypto.Hash import SHA256

def secure_client(url, event_id):
    print(f"🔒 Starting Post-Quantum Secure Client...")
    print(f"📡 Connecting to Server: {url}")
    
    # 1. Get Server's Public Key
    try:
        resp = requests.get(f"{url}/api/pqc/public_key")
        if resp.status_code != 200:
            print("❌ Failed to fetch public key")
            return
        
        pk_hex = resp.json()['public_key']
        server_pk = bytes.fromhex(pk_hex)
        print(f"✅ Received Server Kyber Public Key ({len(pk_hex)//2} bytes)")
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        return

    # 2. Perform Kyber Encapsulation (Client Side)
    # Generate shared secret and ciphertext bound for the server
    # Correct Usage: ss, c = encaps(pk)
    try:
        shared_secret, ciphertext = Kyber1024.encaps(server_pk)
        print(f"🔑 Generated Quantum-Safe Shared Secret")
    except Exception as e:
        print(f"❌ Encapsulation Failed: {e}")
        return

    # 3. Send Ciphertext to Server (Handshake)
    try:
        payload = {'ciphertext': ciphertext.hex()}
        resp = requests.post(f"{url}/api/pqc/handshake", json=payload)
        
        if resp.status_code != 200:
            print(f"❌ Handshake Failed: {resp.text}")
            return
            
        session_token = resp.json()['session_token']
        print(f"🤝 Handshake Success! Session Token: {session_token}")
        
    except Exception as e:
        print(f"❌ Handshake Error: {e}")
        return

    # 4. Request Encrypted Data using Session Token
    try:
        headers = {'X-Session-Token': session_token}
        resp = requests.get(f"{url}/api/pqc/photos/{event_id}", headers=headers)
        
        if resp.status_code != 200:
            print(f"❌ Data Request Failed: {resp.text}")
            return
            
        encrypted_hex = resp.json()['encrypted_data']
        encrypted_blob = bytes.fromhex(encrypted_hex)
        print(f"📦 Received Encrypted Data Packet ({len(encrypted_blob)} bytes)")
        
        # 5. Decrypt Data locally
        # Derive AES key from shared secret (Same KDF as server)
        aes_key = HKDF(shared_secret, salt=None, key_len=32, hashmod=SHA256)
        
        # Unpack nonce, tag, ciphertext
        nonce = encrypted_blob[:12]
        tag = encrypted_blob[12:28]
        ciphertext = encrypted_blob[28:]
        
        cipher = AES.new(aes_key, AES.MODE_GCM, nonce=nonce)
        decrypted_data = cipher.decrypt_and_verify(ciphertext, tag)
        
        print(f"\n🔓 DECRYPTED CONTENT:")
        print(decrypted_data.decode('utf-8'))
        print(f"\n✅ SECURE TRANSFER COMPLETE.")
        
    except ValueError:
        print("❌ Decryption Failed! tamper detection or wrong key.")
    except Exception as e:
        print(f"❌ Processing Error: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Simulate PQC Phone App')
    parser.add_argument('--url', default='http://localhost:8080', help='Server URL')
    parser.add_argument('--event', required=True, help='Event ID to fetch')
    args = parser.parse_args()
    
    secure_client(args.url, args.event)
