import os
import json
import socket
import base64
from crypto_utils.core import *
from config.config import load_dh_public_params, load_server_public_keys, client_store, client_store_lock, TCP_RECV_SIZE
from client.helpers import *
from config.exceptions import *

def login_step_1(cs_socket, username, password, g, N, k):
    seq = 1
    a = generate_dh_private_exponent()
    A = client_srp_dh_public_contribution(g, a, N)
    nonce = generate_nonce()
    server_encryption_public_key, _ = load_server_public_keys()
    
    payload = {
        "seq": seq,
        "username": username,
        "nonce": nonce
    }
    encrypted_payload = asymmetric_encryption(server_encryption_public_key, json.dumps(payload).encode())
    encoded_payload = base64.b64encode(encrypted_payload).decode()
    msg = {
        "metadata": {
            "packet_type": "cs_auth",
            "dh_contribution": A,
        },
        "payload": {
            "cipher_text": encoded_payload 
        }
    }

    packet = json.dumps(msg).encode()
    cs_socket.sendall(packet)
    response = cs_socket.recv(TCP_RECV_SIZE)
    if not response:
        raise ConnectionTerminated("Server has disconnected the session")
    response = json.loads(response.decode())
    
    packet_type = response.get("metadata",{}).get("packet_type")
    match packet_type:
        case "cs_auth":
            metadata = response.get("metadata")
            validate_packet_field(metadata, packet_type=packet_type, field="metadata", seq=2)
            session_key = client_compute_srp_session_key(metadata["salt"], username, password, a, A, metadata["dh_contribution"], g, N, k)
            with client_store_lock:
                client_store.setdefault("server",{})["session_key"] = session_key
            payload = response.get("payload",{}).get("cipher_text")
            decrypted_payload = symmetric_decryption(key=session_key, payload=payload, iv=metadata["iv"], tag=metadata["tag"], aad=packet_type)
            decrypted_payload = json.loads(decrypted_payload.decode())
            current_seq = decrypted_payload["seq"]
            if current_seq != 2:
                raise InvalidSeqNumber("Packet Seq Number is not in order")
            validate_packet_field(decrypted_payload, packet_type="cs_auth", field="payload", seq=current_seq)
            if nonce != decrypted_payload["nonce"]:
                raise InvalidNonce("Nonce doesn't match")
            with client_store_lock:
                client_store.setdefault("server",{})["server_challenge"] = decrypted_payload["server_challenge"]
        case "error":
           handle_pre_auth_error(response, nonce)

def login_step_2(cs_socket):
    seq = 3
    nonce = generate_nonce()
    packet_type = "cs_auth"
    with client_store_lock:
        server_challenge = client_store["server"]["server_challenge"]
        session_key = client_store["server"]["session_key"]
        client_challenge = generate_challenge() 
        client_store["server"]["client_challenge"] = client_challenge

    server_challenge_solution = H(server_challenge) 
    payload = {
        "seq": seq,
        "nonce": nonce,
        "server_challenge_solution": server_challenge_solution,
        "client_challenge": client_challenge
    } 
    result = symmetric_encryption(session_key, json.dumps(payload), aad=packet_type)
    msg = {
        "metadata": {
            "packet_type": "cs_auth",
            "iv": result["iv"],
            "tag": result["tag"]
        },
        "payload": {
            "cipher_text": result["cipher_text"]
        }
    }

    packet = json.dumps(msg).encode()
    cs_socket.sendall(packet)
    response = cs_socket.recv(TCP_RECV_SIZE)
    if not response:
        raise ConnectionTerminated("Server has disconnected the session")
    response = json.loads(response.decode())
    packet_type = response.get("metadata").get("packet_type")
    match packet_type:
        case "cs_auth":
            metadata = response.get("metadata")
            validate_packet_field(metadata, packet_type=packet_type, field="metadata", seq=4)
            payload = response.get("payload").get("cipher_text")
            decrypted_payload = symmetric_decryption(key=session_key, payload=payload, iv=metadata["iv"], tag=metadata["tag"], aad=packet_type)
            decrypted_payload = json.loads(decrypted_payload.decode())
            current_seq = decrypted_payload["seq"]
            if current_seq != 4:
                raise InvalidSeqNumber("Packet Seq Number is not in order")
            validate_packet_field(decrypted_payload, packet_type="cs_auth", field="payload", seq=current_seq)
            if nonce != decrypted_payload["nonce"]:
                raise InvalidNonce("Nonce doesn't match")
            client_challenge_solution = H(client_challenge)
            if client_challenge_solution != decrypted_payload["client_challenge_solution"]:
                raise ChallengeResponseFailed("Server Failed to solve the challenge")
        case "error":
            handle_pre_auth_error(response, nonce)

def login_step_3(cs_socket, username):
    seq = 5
    packet_type = "cs_auth"
    encryption_private_key, encryption_public_key, encryption_pem_public_key = generate_ephemeral_keypairs()
    signiature_private_key, signature_verification_public_key, signature_verification_pem_public_key = generate_ephemeral_keypairs()

    with client_store_lock:
        client_store.setdefault("self",{})["encryption_private_key"] = encryption_private_key
        client_store.setdefault("self",{})["encryption_public_key"] = encryption_public_key
        client_store.setdefault("self",{})["signature_private_key"] = signiature_private_key
        client_store.setdefault("self",{})["signature_verification_public_key"] = signature_verification_public_key
        session_key = client_store["server"]["session_key"]
        listen_address = client_store["self"]["listen_address"]
    
    payload = {
        "seq": seq,
        "username": username,
        "encryption_public_key": base64.b64encode(encryption_pem_public_key).decode(),
        "signature_verification_public_key": base64.b64encode(signature_verification_pem_public_key).decode(),
        "listen_address": listen_address
    } 
    result = symmetric_encryption(session_key, json.dumps(payload),packet_type)
    msg = {
        "metadata": {
            "packet_type": packet_type,
            "iv": result["iv"],
            "tag": result["tag"]
        },
        "payload": {
            "cipher_text": result["cipher_text"]
        }
    }
    packet = json.dumps(msg).encode()
    cs_socket.sendall(packet)

def login(cs_socket: socket.socket):
    """
    Start auth flow
    """
    username = input("Please Enter you Username: ")
    password = input("Please enter your password: ")
    with client_store_lock:
        client_store.setdefault("self",{})["username"] = username
    g, N, k = load_dh_public_params()
    login_step_1(cs_socket, username, password, g, N, k)
    login_step_2(cs_socket)
    login_step_3(cs_socket, username)
    

    


