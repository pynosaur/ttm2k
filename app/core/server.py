#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ttm2k relay server.

Handles client connections, authentication, presence, and message routing.
Users are stored in a simple JSON file on disk. All message content is
end-to-end encrypted between clients -- the server only sees ciphertext.
"""

import json
import os
import select
import socket
import struct
import threading
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

from app.core import protocol
from app.core.crypto import hash_password, verify_password


DEFAULT_PORT = 2000
BACKLOG = 32
RECV_BUF = 4096


class UserStore:
    """Flat-file user database."""

    def __init__(self, path: str):
        self.path = Path(path)
        self._lock = threading.Lock()
        self._users: Dict[str, dict] = {}
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text())
                self._users = data
            except (json.JSONDecodeError, OSError):
                self._users = {}

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix('.tmp')
        tmp.write_text(json.dumps(self._users, indent=2))
        tmp.replace(self.path)

    def register(self, username: str, password: str) -> bool:
        with self._lock:
            if username in self._users:
                return False
            pw_hash, salt = hash_password(password)
            self._users[username] = {
                "hash": pw_hash.hex(),
                "salt": salt.hex(),
                "created": time.time(),
            }
            self._save()
            return True

    def authenticate(self, username: str, password: str) -> bool:
        with self._lock:
            user = self._users.get(username)
            if not user:
                return False
            stored_hash = bytes.fromhex(user["hash"])
            salt = bytes.fromhex(user["salt"])
            return verify_password(password, stored_hash, salt)

    def exists(self, username: str) -> bool:
        return username in self._users

    def list_users(self) -> list:
        return list(self._users.keys())


class ClientConnection:
    """State for a single connected client."""

    def __init__(self, sock: socket.socket, addr: Tuple[str, int]):
        self.sock = sock
        self.addr = addr
        self.username: Optional[str] = None
        self.status: str = protocol.STATUS_ONLINE
        self.status_msg: str = ""
        self.authenticated: bool = False
        self._recv_buf = b""

    def fileno(self):
        return self.sock.fileno()

    def send_msg(self, msg: dict):
        try:
            frame = protocol.encode_frame(msg)
            self.sock.sendall(frame)
        except OSError:
            pass

    def recv_frames(self) -> list:
        """Read available data and return complete message dicts."""
        try:
            data = self.sock.recv(RECV_BUF)
            if not data:
                return []
            self._recv_buf += data
        except OSError:
            return []

        frames = []
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
                frames.append(msg)
        return frames


class Server:
    """ttm2k relay server."""

    def __init__(self, host: str = "0.0.0.0", port: int = DEFAULT_PORT,
                 data_dir: str = "~/.ttm2k/server"):
        self.host = host
        self.port = port
        self.data_dir = Path(os.path.expanduser(data_dir))
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.users = UserStore(str(self.data_dir / "users.json"))
        self.clients: Dict[int, ClientConnection] = {}
        self.online: Dict[str, ClientConnection] = {}
        self._lock = threading.Lock()
        self._running = False
        self._server_sock: Optional[socket.socket] = None

    def start(self):
        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind((self.host, self.port))
        self._server_sock.listen(BACKLOG)
        self._server_sock.setblocking(False)
        self._running = True

        print(f"ttm2k server listening on {self.host}:{self.port}")
        print(f"data directory: {self.data_dir}")

        try:
            self._loop()
        except KeyboardInterrupt:
            print("\nshutting down...")
        finally:
            self._shutdown()

    def _loop(self):
        while self._running:
            read_list = [self._server_sock] + list(self.clients.values())
            try:
                readable, _, _ = select.select(read_list, [], [], 1.0)
            except (ValueError, OSError):
                continue

            for obj in readable:
                if obj is self._server_sock:
                    self._accept()
                else:
                    self._handle_client(obj)

    def _accept(self):
        try:
            sock, addr = self._server_sock.accept()
            sock.setblocking(False)
            client = ClientConnection(sock, addr)
            self.clients[sock.fileno()] = client
            print(f"[+] connection from {addr[0]}:{addr[1]}")
        except OSError:
            pass

    def _handle_client(self, client: ClientConnection):
        frames = client.recv_frames()
        if not frames:
            self._disconnect(client)
            return

        for msg in frames:
            self._dispatch(client, msg)

    def _dispatch(self, client: ClientConnection, msg: dict):
        msg_type = msg.get("type", "")

        if msg_type == protocol.MSG_AUTH:
            self._handle_auth(client, msg)
        elif msg_type == protocol.MSG_REGISTER:
            self._handle_register(client, msg)
        elif not client.authenticated:
            client.send_msg(protocol.make_error("not authenticated"))
            return
        elif msg_type == protocol.MSG_CHAT:
            self._handle_chat(client, msg)
        elif msg_type == protocol.MSG_NUDGE:
            self._handle_nudge(client, msg)
        elif msg_type == protocol.MSG_TYPING:
            self._handle_typing(client, msg)
        elif msg_type == protocol.MSG_STATUS:
            self._handle_status(client, msg)
        elif msg_type == protocol.MSG_KEY_EXCHANGE:
            self._relay_to_target(msg)
        elif msg_type == protocol.MSG_KEY_REPLY:
            self._relay_to_target(msg)
        elif msg_type == protocol.MSG_DISCONNECT:
            self._disconnect(client)

    def _handle_auth(self, client: ClientConnection, msg: dict):
        username = msg.get("user", "").strip()
        password = msg.get("pass", "")

        if not username or not password:
            client.send_msg(protocol.make_auth_fail("missing credentials"))
            return

        if self.users.authenticate(username, password):
            with self._lock:
                old = self.online.get(username)
                if old and old is not client:
                    old.send_msg(
                        protocol.make_server_msg("signed in from another location")
                    )
                    self._disconnect(old, broadcast=False)

                client.username = username
                client.authenticated = True
                self.online[username] = client

            client.send_msg({"type": protocol.MSG_AUTH_OK, "user": username})
            self._broadcast_presence(username, protocol.STATUS_ONLINE)
            self._send_buddy_list(client)
            print(f"[*] {username} signed in")
        else:
            client.send_msg({"type": protocol.MSG_AUTH_FAIL, "text": "bad credentials"})

    def _handle_register(self, client: ClientConnection, msg: dict):
        username = msg.get("user", "").strip()
        password = msg.get("pass", "")

        if not username or len(username) < 2 or len(username) > 24:
            client.send_msg({
                "type": protocol.MSG_REGISTER_FAIL,
                "text": "username must be 2-24 characters",
            })
            return

        if not all(c.isalnum() or c in '-_.' for c in username):
            client.send_msg({
                "type": protocol.MSG_REGISTER_FAIL,
                "text": "username: letters, numbers, -, _, . only",
            })
            return

        if len(password) < 4:
            client.send_msg({
                "type": protocol.MSG_REGISTER_FAIL,
                "text": "password must be at least 4 characters",
            })
            return

        if self.users.register(username, password):
            client.send_msg({
                "type": protocol.MSG_REGISTER_OK,
                "user": username,
            })
            print(f"[+] registered new user: {username}")
        else:
            client.send_msg({
                "type": protocol.MSG_REGISTER_FAIL,
                "text": "username already taken",
            })

    def _handle_chat(self, client: ClientConnection, msg: dict):
        target = msg.get("to", "")
        msg["from"] = client.username
        self._relay_to_target(msg)
        client.send_msg({"type": protocol.MSG_CHAT_ACK, "ts": msg.get("ts", 0)})

    def _handle_nudge(self, client: ClientConnection, msg: dict):
        msg["from"] = client.username
        self._relay_to_target(msg)

    def _handle_typing(self, client: ClientConnection, msg: dict):
        msg["from"] = client.username
        self._relay_to_target(msg)

    def _handle_status(self, client: ClientConnection, msg: dict):
        client.status = msg.get("status", protocol.STATUS_ONLINE)
        client.status_msg = msg.get("message", "")
        self._broadcast_presence(
            client.username, client.status, client.status_msg
        )

    def _relay_to_target(self, msg: dict):
        target = msg.get("to", "")
        with self._lock:
            peer = self.online.get(target)
        if peer:
            peer.send_msg(msg)

    def _broadcast_presence(self, username: str, status: str, message: str = ""):
        update = protocol.make_buddy_update(username, status, message)
        with self._lock:
            for name, client in self.online.items():
                if name != username:
                    client.send_msg(update)

    def _send_buddy_list(self, client: ClientConnection):
        with self._lock:
            buddies = []
            for name, c in self.online.items():
                if name != client.username:
                    buddies.append({
                        "user": name,
                        "status": c.status,
                        "message": c.status_msg,
                    })
        all_users = self.users.list_users()
        for u in all_users:
            if u != client.username and u not in self.online:
                buddies.append({
                    "user": u,
                    "status": protocol.STATUS_OFFLINE,
                    "message": "",
                })
        client.send_msg(protocol.make_buddy_list(buddies))

    def _disconnect(self, client: ClientConnection, broadcast: bool = True):
        fd = client.sock.fileno()
        username = client.username

        with self._lock:
            self.clients.pop(fd, None)
            if username and self.online.get(username) is client:
                del self.online[username]

        try:
            client.sock.close()
        except OSError:
            pass

        if username:
            if broadcast:
                self._broadcast_presence(username, protocol.STATUS_OFFLINE)
            print(f"[-] {username} disconnected")
        else:
            print(f"[-] {client.addr[0]}:{client.addr[1]} disconnected")

    def _shutdown(self):
        with self._lock:
            for client in list(self.clients.values()):
                try:
                    client.sock.close()
                except OSError:
                    pass
            self.clients.clear()
            self.online.clear()

        if self._server_sock:
            try:
                self._server_sock.close()
            except OSError:
                pass
        self._running = False


def make_auth_fail(text: str) -> dict:
    return {"type": protocol.MSG_AUTH_FAIL, "text": text}
