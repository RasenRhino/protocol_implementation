# server_models.py

from dataclasses import dataclass
from typing import Optional
from server_constants import PacketType, ProtocolState

@dataclass
class User:
    username: str
    encryption_public_key: str
    signing_public_key: str
    listen_address: str

@dataclass
class Metadata:
    packet_type: PacketType
    state: Optional[ProtocolState] = None
    salt: Optional[str] = None
    dh_contribution: Optional[int] = None
    iv: Optional[str] = None
    tag: Optional[str] = None
    error_count: Optional[int] = None

@dataclass
class Payload:
    seq: Optional[int] = None
    username: Optional[str] = None
    nonce: Optional[str] = None
    server_challenge: Optional[str] = None
    server_challenge_solution: Optional[str] = None
    client_challenge: Optional[str] = None
    client_challenge_solution: Optional[str] = None
    encryption_public_key: Optional[str] = None
    signature_verification_public_key: Optional[str] = None
    listen_address: Optional[str] = None
    message: Optional[str] = None
    signature: Optional[str] = None
    cipher_text: Optional[str] = None
    recipient : Optional[str] = None
    packet_type: Optional[PacketType] = None

@dataclass
class Message:
    metadata: Optional[Metadata] = None
    payload: Payload = None
