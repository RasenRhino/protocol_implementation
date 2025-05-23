# src/crypto_utils/core.py
import random
import secrets
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
import os
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
import base64
import hashlib
from cryptography.exceptions import InvalidSignature, InvalidTag
from argon2 import PasswordHasher
from argon2.low_level import hash_secret_raw, Type

def load_private_key(file_path: str):
    """
    Load a private key from a file. 

    :param file_path: Path to the private key file.
    :return: a private key object.
    """
    with open(file_path, "rb") as f:
        key_data = f.read()
        return serialization.load_pem_private_key(key_data, password=None )

def load_public_key_from_bytes(public_key: str):
    return serialization.load_pem_public_key(
        base64.b64decode(public_key),
    )


def load_public_key(file_path: str):
    """
    Load a public key from a file.
    :param file_path: Path to the public key file.
    :return: a public key object.
    """
    with open(file_path, "rb") as f:
        key_data = f.read()
        return serialization.load_pem_public_key(key_data)



def asymmetric_decryption(private_key: bytes, ciphertext: bytes) -> bytes:
    """
    Decrypt an RSA OAEP ciphertext using the given private key.

    :param private_key: RSA private key object.
    :param ciphertext: The ciphertext bytes to decrypt.
    :return: The decrypted plaintext message as bytes.
    :raises ValueError: If the decryption fails (e.g., wrong key, corrupted data).
    """
    plaintext = private_key.decrypt(
        ciphertext,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    return plaintext

def generate_signature(payload: str, private_key: bytes):
    return base64.b64encode(private_key.sign(
        payload.encode(),
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
        hashes.SHA256()
    )).decode()

def verify_signature(payload: str, signature: str, public_key: bytes):
    is_valid = False
    try:
        public_key.verify(
            base64.b64decode(signature),
            payload.encode(),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        is_valid = True
    except InvalidSignature:
        print("Signature is invalid")
    finally:
        return is_valid

def generate_nonce():
    return secrets.token_hex(16)   
def generate_challenge():
    return secrets.token_hex(16)   
def SHA3_512(data:str):
    digest = hashes.Hash(hashes.SHA3_512())
    digest.update(data.encode('utf-8'))
    return base64.b64encode(digest.finalize()).decode('utf-8')
def symmetric_decryption(key: bytes, payload:str,iv:str, tag: str, aad: str) -> bytes:
    """
    Decrypt AES-GCM encrypted data.
    :param key: The symmetric AES key.
    :param payload: The ciphertext.
    :param iv: Initialization vector (nonce) used during encryption.
    :param tag: Authentication tag generated during encryption.
    :param aad: Additional authenticated data used in encryption.
    :return: Decrypted plaintext bytes.
    """
    iv = base64.b64decode(iv)
    tag=base64.b64decode(tag)
    payload= base64.b64decode(payload)
    aad=aad.encode('utf-8')
    cipher = Cipher(algorithms.AES(key), modes.GCM(iv, tag))
    decryptor = cipher.decryptor()
    #pls validate aad==packet_type in client side code
    decryptor.authenticate_additional_data(aad)
    # Perform decryption
    plaintext = decryptor.update(payload) + decryptor.finalize()
    return plaintext
def symmetric_encryption(key: bytes, payload: str, aad: str) -> dict:
    """
    Encrypts a plaintext payload using AES-GCM with the provided key and additional authenticated data (AAD).

    Args:
        key (bytes): A symmetric key for AES encryption. Should be 16, 24, or 32 bytes long.
        payload (str): The plaintext message to encrypt.
        aad (str): Additional Authenticated Data (AAD) to bind to the ciphertext. This data will not be encrypted,
                   but any tampering will be detected upon decryption.
                   'packet_type' is used as AAD.

    Returns:
        dict: A dictionary containing:
            - 'cipher_text': The encrypted payload (base64-encoded).
            - 'iv': The initialization vector used in encryption (base64-encoded).
            - 'tag': The GCM authentication tag (base64-encoded).
            - 'AAD': The original AAD, also base64-encoded for transmission/storage.
    """
    associated_data = aad.encode('utf-8')
    iv = os.urandom(12)
    cipher = Cipher(algorithms.AES(key), modes.GCM(iv))
    encryptor = cipher.encryptor()
    encryptor.authenticate_additional_data(associated_data)

    payload = payload.encode('utf-8')
    cipher_text = encryptor.update(payload) + encryptor.finalize()
    tag = encryptor.tag

    return {
        "cipher_text": base64.b64encode(cipher_text).decode('utf-8'),
        "iv": base64.b64encode(iv).decode('utf-8'),
        "tag": base64.b64encode(tag).decode('utf-8'),
        "AAD": base64.b64encode(associated_data).decode('utf-8')
    }

def asymmetric_encryption(public_key: bytes, message: bytes) -> bytes:
    """
    Encrypt a message using RSA OAEP with SHA-256.

    :param public_key: RSA public key object.
    :param message: The plaintext message to encrypt.
    :return: The RSA-encrypted ciphertext as bytes.
    """
    ciphertext = public_key.encrypt(
        message,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    return ciphertext

def generate_dh_private_exponent(n_bytes=32):
    return int.from_bytes(os.urandom(n_bytes), byteorder="big")

def H(*args):
    a = ":".join(str(a) for a in args)
    return int(hashlib.sha3_512(a.encode()).hexdigest(), 16)

def argon2_hash(salt, username, password):
    a = f"{username}:{password}".encode()
    hash_bytes = hash_secret_raw(
        secret=a,
        salt=salt.encode(),
        time_cost=3,      
        memory_cost=65536,
        parallelism=2,
        hash_len=32,
        type=Type.I 
    )
    return int.from_bytes(hash_bytes, byteorder='big')

def compute_dh_key(C, e, N):
    return hashlib.sha3_512(str(pow(C, e, N)).encode()).digest()[:32]

def client_srp_dh_public_contribution(g, a, N):
    return pow(g, a, N)

def client_compute_srp_session_key(salt, username, password, a, A, B, g, N, k):
    if((B%N)== 0):
        raise ValueError("Server public key is zero")
    x = argon2_hash(salt, username, password)
    u = H(A, B)
    S_c = pow(B - (k * pow(g, x, N)), a + (u * x), N)
    K_c = H(S_c)
    return hashlib.sha3_512(str(K_c).encode()).digest()[:32]

def server_srp_dh_public_contribution(k, v, b, g, N):
    B = (k * v + pow(g, b, N)) % N
    return B

def server_compute_srp_session_key(k, v, b, B, A, N):
    if((A%N)== 0):
        raise ValueError("Client public key is zero")
    u = H(A, B)
    S_s = pow(A * pow(v, u, N), b, N)
    K_s = H(S_s)
    return hashlib.sha3_512(str(K_s).encode()).digest()[:32]

def generate_server_key(k,v,A,g,N) -> dict:
    b=generate_dh_private_exponent()
    B=server_srp_dh_public_contribution(k,v,b,g,N)
    key=server_compute_srp_session_key(k, v, b, B, A, N)
    return (B,key)

def generate_ephemeral_keypairs():
    private_key = rsa.generate_private_key(
        public_exponent=65537,  # Standard public exponent
        key_size=2048,  # Key size in bits (2048 is a common choice for good security)  
    )
    public_key = private_key.public_key()
    pem_public_key = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return (private_key,public_key, pem_public_key)   

def generate_random_port():
    return random.randint(4000,60000)