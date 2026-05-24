#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Wire protocol for ttm2k.

Messages are length-prefixed JSON frames:
    [4 bytes big-endian length][JSON payload]

Binary payloads (encrypted messages, DH keys) are base64-encoded
inside the JSON so the framing stays text-safe.
"""

import base64
import json
import struct
import time
from typing import Dict, Any, Optional

MSG_AUTH = "auth"
MSG_AUTH_OK = "auth_ok"
MSG_AUTH_FAIL = "auth_fail"
MSG_REGISTER = "register"
MSG_REGISTER_OK = "register_ok"
MSG_REGISTER_FAIL = "register_fail"
MSG_CHAT = "chat"
MSG_CHAT_ACK = "chat_ack"
MSG_STATUS = "status"
MSG_NUDGE = "nudge"
MSG_TYPING = "typing"
MSG_BUDDY_LIST = "buddy_list"
MSG_BUDDY_UPDATE = "buddy_update"
MSG_KEY_EXCHANGE = "key_exchange"
MSG_KEY_REPLY = "key_reply"
MSG_SERVER_MSG = "server_msg"
MSG_DISCONNECT = "disconnect"
MSG_ERROR = "error"

STATUS_ONLINE = "online"
STATUS_AWAY = "away"
STATUS_BUSY = "busy"
STATUS_BRB = "brb"
STATUS_OFFLINE = "offline"

HEADER_SIZE = 4
MAX_MSG_SIZE = 1024 * 1024  # 1 MB


def encode_frame(msg: Dict[str, Any]) -> bytes:
    """Encode a message dict into a length-prefixed frame."""
    payload = json.dumps(msg, separators=(',', ':')).encode('utf-8')
    if len(payload) > MAX_MSG_SIZE:
        raise ValueError("message too large")
    return struct.pack('>I', len(payload)) + payload


def decode_frame(data: bytes) -> Optional[Dict[str, Any]]:
    """Decode a JSON payload from raw bytes (without length prefix)."""
    try:
        return json.loads(data.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def pack_bytes(raw: bytes) -> str:
    """Base64-encode bytes for JSON transport."""
    return base64.b64encode(raw).decode('ascii')


def unpack_bytes(encoded: str) -> bytes:
    """Decode base64 string back to bytes."""
    return base64.b64decode(encoded)


def make_auth(username: str, password: str) -> Dict[str, Any]:
    return {"type": MSG_AUTH, "user": username, "pass": password}


def make_register(username: str, password: str) -> Dict[str, Any]:
    return {"type": MSG_REGISTER, "user": username, "pass": password}


def make_chat(
    sender: str, target: str, encrypted_payload: bytes
) -> Dict[str, Any]:
    return {
        "type": MSG_CHAT,
        "from": sender,
        "to": target,
        "payload": pack_bytes(encrypted_payload),
        "ts": time.time(),
    }


def make_nudge(sender: str, target: str) -> Dict[str, Any]:
    return {"type": MSG_NUDGE, "from": sender, "to": target, "ts": time.time()}


def make_typing(sender: str, target: str, is_typing: bool) -> Dict[str, Any]:
    return {
        "type": MSG_TYPING,
        "from": sender,
        "to": target,
        "typing": is_typing,
    }


def make_status(username: str, status: str, message: str = "") -> Dict[str, Any]:
    return {
        "type": MSG_STATUS,
        "user": username,
        "status": status,
        "message": message,
    }


def make_key_exchange(sender: str, target: str, public_key: bytes) -> Dict[str, Any]:
    return {
        "type": MSG_KEY_EXCHANGE,
        "from": sender,
        "to": target,
        "key": pack_bytes(public_key),
    }


def make_key_reply(sender: str, target: str, public_key: bytes) -> Dict[str, Any]:
    return {
        "type": MSG_KEY_REPLY,
        "from": sender,
        "to": target,
        "key": pack_bytes(public_key),
    }


def make_buddy_list(buddies: list) -> Dict[str, Any]:
    return {"type": MSG_BUDDY_LIST, "buddies": buddies}


def make_buddy_update(
    username: str, status: str, message: str = ""
) -> Dict[str, Any]:
    return {
        "type": MSG_BUDDY_UPDATE,
        "user": username,
        "status": status,
        "message": message,
    }


def make_server_msg(text: str) -> Dict[str, Any]:
    return {"type": MSG_SERVER_MSG, "text": text, "ts": time.time()}


def make_error(text: str) -> Dict[str, Any]:
    return {"type": MSG_ERROR, "text": text}
