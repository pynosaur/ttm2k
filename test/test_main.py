#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.crypto import (
    DHKeyPair,
    derive_keys,
    encrypt,
    decrypt,
    hash_password,
    verify_password,
)
from app.core.protocol import (
    encode_frame,
    decode_frame,
    pack_bytes,
    unpack_bytes,
    make_auth,
    make_chat,
    make_nudge,
    make_status,
    make_key_exchange,
    HEADER_SIZE,
)
from app.core.art import (
    box,
    thin_box,
    gradient_bar,
    center_text,
    format_timestamp,
    STATUS_ICONS,
)


class TestCrypto(unittest.TestCase):
    """Test cryptographic primitives."""

    def test_dh_key_exchange(self):
        alice = DHKeyPair()
        bob = DHKeyPair()
        shared_a = alice.derive_shared(bob.public)
        shared_b = bob.derive_shared(alice.public)
        self.assertEqual(shared_a, shared_b)

    def test_dh_public_serialization(self):
        kp = DHKeyPair()
        pub_bytes = kp.public_bytes()
        self.assertEqual(len(pub_bytes), 256)
        restored = DHKeyPair.public_from_bytes(pub_bytes)
        self.assertEqual(restored, kp.public)

    def test_encrypt_decrypt_roundtrip(self):
        alice = DHKeyPair()
        bob = DHKeyPair()
        shared = alice.derive_shared(bob.public)
        enc_key, mac_key = derive_keys(shared)

        message = b"Talk To Me 2000!"
        ciphertext = encrypt(message, enc_key, mac_key)
        plaintext = decrypt(ciphertext, enc_key, mac_key)
        self.assertEqual(plaintext, message)

    def test_decrypt_tampered_fails(self):
        alice = DHKeyPair()
        bob = DHKeyPair()
        shared = alice.derive_shared(bob.public)
        enc_key, mac_key = derive_keys(shared)

        ciphertext = encrypt(b"secret", enc_key, mac_key)
        tampered = bytearray(ciphertext)
        tampered[20] ^= 0xFF
        self.assertIsNone(decrypt(bytes(tampered), enc_key, mac_key))

    def test_decrypt_wrong_key_fails(self):
        alice = DHKeyPair()
        bob = DHKeyPair()
        eve = DHKeyPair()

        shared_ab = alice.derive_shared(bob.public)
        shared_ae = alice.derive_shared(eve.public)

        enc_key_ab, mac_key_ab = derive_keys(shared_ab)
        enc_key_ae, mac_key_ae = derive_keys(shared_ae)

        ciphertext = encrypt(b"secret", enc_key_ab, mac_key_ab)
        self.assertIsNone(decrypt(ciphertext, enc_key_ae, mac_key_ae))

    def test_encrypt_produces_different_ciphertexts(self):
        enc_key = b'\x01' * 32
        mac_key = b'\x02' * 32
        msg = b"same message"
        c1 = encrypt(msg, enc_key, mac_key)
        c2 = encrypt(msg, enc_key, mac_key)
        self.assertNotEqual(c1, c2)

    def test_password_hashing(self):
        pw_hash, salt = hash_password("y2k_forever")
        self.assertTrue(verify_password("y2k_forever", pw_hash, salt))
        self.assertFalse(verify_password("wrong_password", pw_hash, salt))


class TestProtocol(unittest.TestCase):
    """Test wire protocol framing and message construction."""

    def test_frame_roundtrip(self):
        msg = {"type": "test", "data": "hello"}
        frame = encode_frame(msg)
        self.assertEqual(len(frame), HEADER_SIZE + len(frame) - HEADER_SIZE)
        decoded = decode_frame(frame[HEADER_SIZE:])
        self.assertEqual(decoded, msg)

    def test_bytes_packing(self):
        raw = b'\x00\x01\x02\xff'
        encoded = pack_bytes(raw)
        self.assertIsInstance(encoded, str)
        decoded = unpack_bytes(encoded)
        self.assertEqual(decoded, raw)

    def test_make_auth(self):
        msg = make_auth("alice", "password123")
        self.assertEqual(msg["type"], "auth")
        self.assertEqual(msg["user"], "alice")

    def test_make_chat(self):
        msg = make_chat("alice", "bob", b"encrypted_data")
        self.assertEqual(msg["type"], "chat")
        self.assertEqual(msg["from"], "alice")
        self.assertEqual(msg["to"], "bob")
        self.assertIn("ts", msg)

    def test_make_nudge(self):
        msg = make_nudge("alice", "bob")
        self.assertEqual(msg["type"], "nudge")

    def test_make_status(self):
        msg = make_status("alice", "away", "brb lunch")
        self.assertEqual(msg["status"], "away")
        self.assertEqual(msg["message"], "brb lunch")

    def test_make_key_exchange(self):
        msg = make_key_exchange("alice", "bob", b'\x42' * 256)
        self.assertEqual(msg["type"], "key_exchange")
        raw = unpack_bytes(msg["key"])
        self.assertEqual(len(raw), 256)


class TestArt(unittest.TestCase):
    """Test art/visual elements."""

    def test_box_dimensions(self):
        lines = box(20, 5)
        self.assertEqual(len(lines), 5)
        self.assertEqual(len(lines[0]), 20)

    def test_thin_box_dimensions(self):
        lines = thin_box(30, 4, "Title")
        self.assertEqual(len(lines), 4)

    def test_gradient_bar_length(self):
        bar = gradient_bar(40)
        self.assertEqual(len(bar), 40)

    def test_center_text(self):
        result = center_text("hi", 10)
        self.assertEqual(len(result), 10)
        self.assertIn("hi", result)

    def test_format_timestamp(self):
        import time
        ts = time.time()
        result = format_timestamp(ts)
        self.assertEqual(len(result), 5)
        self.assertIn(":", result)

    def test_status_icons_complete(self):
        expected = {"online", "away", "busy", "brb", "offline"}
        self.assertEqual(set(STATUS_ICONS.keys()), expected)


class TestIntegration(unittest.TestCase):
    """Integration tests for client-server interaction."""

    def test_help_output(self):
        import subprocess
        result = subprocess.run(
            [sys.executable, "app/main.py", "--help"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parent.parent),
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("ttm2k", result.stdout)
        self.assertIn("Talk To Me 2000", result.stdout)

    def test_version_output(self):
        import subprocess
        result = subprocess.run(
            [sys.executable, "app/main.py", "--version"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parent.parent),
        )
        self.assertEqual(result.returncode, 0)
        from app import __version__
        self.assertIn(__version__, result.stdout)


if __name__ == "__main__":
    unittest.main()
