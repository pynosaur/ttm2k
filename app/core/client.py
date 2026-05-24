#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ttm2k network client.

Handles the TCP connection to the relay server, frame I/O on a background
thread, and exposes a callback-driven API that the UI layer consumes.
"""

import socket
import struct
import threading
import time
from typing import Callable, Dict, Optional, Tuple

from app.core import protocol
from app.core.crypto import DHKeyPair, derive_keys, encrypt, decrypt


RECV_BUF = 4096


class PeerSession:
    """E2E encrypted session with a single peer."""

    def __init__(self, peer: str):
        self.peer = peer
        self.dh: Optional[DHKeyPair] = None
        self.enc_key: Optional[bytes] = None
        self.mac_key: Optional[bytes] = None
        self.established = False
        self.initiator = False

    def start_exchange(self) -> bytes:
        self.dh = DHKeyPair()
        self.initiator = True
        return self.dh.public_bytes()

    def complete_exchange(self, peer_public_bytes: bytes):
        if self.dh is None:
            self.dh = DHKeyPair()
        peer_pub = DHKeyPair.public_from_bytes(peer_public_bytes)
        shared = self.dh.derive_shared(peer_pub)
        self.enc_key, self.mac_key = derive_keys(shared)
        self.established = True

    def encrypt_msg(self, plaintext: str) -> Optional[bytes]:
        if not self.established:
            return None
        return encrypt(plaintext.encode('utf-8'), self.enc_key, self.mac_key)

    def decrypt_msg(self, data: bytes) -> Optional[str]:
        if not self.established:
            return None
        pt = decrypt(data, self.enc_key, self.mac_key)
        if pt is None:
            return None
        return pt.decode('utf-8', errors='replace')


class Client:
    """ttm2k client -- connects to server, manages E2E sessions."""

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.username: Optional[str] = None
        self.sock: Optional[socket.socket] = None
        self._recv_buf = b""
        self._running = False
        self._reader_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        self.sessions: Dict[str, PeerSession] = {}
        self.buddies: Dict[str, dict] = {}

        self.on_message: Optional[Callable] = None
        self.on_nudge: Optional[Callable] = None
        self.on_typing: Optional[Callable] = None
        self.on_buddy_list: Optional[Callable] = None
        self.on_buddy_update: Optional[Callable] = None
        self.on_server_msg: Optional[Callable] = None
        self.on_auth_ok: Optional[Callable] = None
        self.on_auth_fail: Optional[Callable] = None
        self.on_register_ok: Optional[Callable] = None
        self.on_register_fail: Optional[Callable] = None
        self.on_key_established: Optional[Callable] = None
        self.on_disconnect: Optional[Callable] = None
        self.on_error: Optional[Callable] = None

    def connect(self) -> bool:
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5.0)
            self.sock.connect((self.host, self.port))
            self.sock.settimeout(None)
            self._running = True
            self._reader_thread = threading.Thread(
                target=self._reader_loop, daemon=True
            )
            self._reader_thread.start()
            return True
        except OSError:
            return False

    def disconnect(self):
        self._running = False
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass
        self.sock = None

    def login(self, username: str, password: str):
        self._send(protocol.make_auth(username, password))

    def register(self, username: str, password: str):
        self._send(protocol.make_register(username, password))

    def send_chat(self, target: str, text: str) -> bool:
        session = self._get_or_create_session(target)
        if not session.established:
            self._initiate_key_exchange(target)
            return False
        encrypted = session.encrypt_msg(text)
        if encrypted is None:
            return False
        self._send(protocol.make_chat(self.username, target, encrypted))
        return True

    def send_nudge(self, target: str):
        self._send(protocol.make_nudge(self.username, target))

    def send_typing(self, target: str, is_typing: bool):
        self._send(protocol.make_typing(self.username, target, is_typing))

    def set_status(self, status: str, message: str = ""):
        self._send(protocol.make_status(self.username, status, message))

    def _initiate_key_exchange(self, peer: str):
        session = self._get_or_create_session(peer)
        pub_bytes = session.start_exchange()
        self._send(protocol.make_key_exchange(self.username, peer, pub_bytes))

    def _get_or_create_session(self, peer: str) -> PeerSession:
        with self._lock:
            if peer not in self.sessions:
                self.sessions[peer] = PeerSession(peer)
            return self.sessions[peer]

    def _send(self, msg: dict):
        if self.sock is None:
            return
        try:
            frame = protocol.encode_frame(msg)
            self.sock.sendall(frame)
        except OSError:
            self._handle_disconnect()

    def _reader_loop(self):
        while self._running and self.sock:
            try:
                data = self.sock.recv(RECV_BUF)
                if not data:
                    self._handle_disconnect()
                    return
                self._recv_buf += data
                self._process_frames()
            except OSError:
                if self._running:
                    self._handle_disconnect()
                return

    def _process_frames(self):
        while len(self._recv_buf) >= protocol.HEADER_SIZE:
            msg_len = struct.unpack('>I', self._recv_buf[:4])[0]
            if msg_len > protocol.MAX_MSG_SIZE:
                self._recv_buf = b""
                break
            total = protocol.HEADER_SIZE + msg_len
            if len(self._recv_buf) < total:
                break
            payload = self._recv_buf[protocol.HEADER_SIZE:total]
            self._recv_buf = self._recv_buf[total:]
            msg = protocol.decode_frame(payload)
            if msg:
                self._dispatch(msg)

    def _dispatch(self, msg: dict):
        t = msg.get("type", "")

        if t == protocol.MSG_AUTH_OK:
            self.username = msg.get("user", "")
            if self.on_auth_ok:
                self.on_auth_ok(msg)

        elif t == protocol.MSG_AUTH_FAIL:
            if self.on_auth_fail:
                self.on_auth_fail(msg.get("text", "authentication failed"))

        elif t == protocol.MSG_REGISTER_OK:
            if self.on_register_ok:
                self.on_register_ok(msg)

        elif t == protocol.MSG_REGISTER_FAIL:
            if self.on_register_fail:
                self.on_register_fail(msg.get("text", "registration failed"))

        elif t == protocol.MSG_CHAT:
            self._handle_incoming_chat(msg)

        elif t == protocol.MSG_NUDGE:
            if self.on_nudge:
                self.on_nudge(msg.get("from", ""))

        elif t == protocol.MSG_TYPING:
            if self.on_typing:
                self.on_typing(msg.get("from", ""), msg.get("typing", False))

        elif t == protocol.MSG_BUDDY_LIST:
            self._handle_buddy_list(msg)

        elif t == protocol.MSG_BUDDY_UPDATE:
            self._handle_buddy_update(msg)

        elif t == protocol.MSG_KEY_EXCHANGE:
            self._handle_key_exchange(msg)

        elif t == protocol.MSG_KEY_REPLY:
            self._handle_key_reply(msg)

        elif t == protocol.MSG_SERVER_MSG:
            if self.on_server_msg:
                self.on_server_msg(msg.get("text", ""))

        elif t == protocol.MSG_ERROR:
            if self.on_error:
                self.on_error(msg.get("text", "unknown error"))

    def _handle_incoming_chat(self, msg: dict):
        sender = msg.get("from", "")
        session = self._get_or_create_session(sender)

        if not session.established:
            if self.on_message:
                self.on_message(sender, "[encrypted -- key exchange pending]")
            return

        payload = protocol.unpack_bytes(msg.get("payload", ""))
        text = session.decrypt_msg(payload)
        if text is None:
            if self.on_message:
                self.on_message(sender, "[decryption failed]")
            return

        if self.on_message:
            self.on_message(sender, text)

    def _handle_key_exchange(self, msg: dict):
        sender = msg.get("from", "")
        peer_key = protocol.unpack_bytes(msg.get("key", ""))
        session = self._get_or_create_session(sender)

        session.dh = DHKeyPair()
        session.complete_exchange(peer_key)
        reply_pub = session.dh.public_bytes()
        self._send(protocol.make_key_reply(self.username, sender, reply_pub))

        if self.on_key_established:
            self.on_key_established(sender)

    def _handle_key_reply(self, msg: dict):
        sender = msg.get("from", "")
        peer_key = protocol.unpack_bytes(msg.get("key", ""))
        session = self._get_or_create_session(sender)
        session.complete_exchange(peer_key)

        if self.on_key_established:
            self.on_key_established(sender)

    def _handle_buddy_list(self, msg: dict):
        buddies = msg.get("buddies", [])
        with self._lock:
            self.buddies = {b["user"]: b for b in buddies}
        if self.on_buddy_list:
            self.on_buddy_list(buddies)

    def _handle_buddy_update(self, msg: dict):
        user = msg.get("user", "")
        status = msg.get("status", protocol.STATUS_OFFLINE)
        message = msg.get("message", "")
        with self._lock:
            self.buddies[user] = {
                "user": user,
                "status": status,
                "message": message,
            }
        if self.on_buddy_update:
            self.on_buddy_update(user, status, message)

    def _handle_disconnect(self):
        self._running = False
        if self.on_disconnect:
            self.on_disconnect()
