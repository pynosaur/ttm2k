#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cryptography module for ttm2k.

Implements Diffie-Hellman key exchange and HMAC-SHA256 based symmetric
encryption using only the Python standard library. Not a substitute for
a vetted TLS library in production, but solid for a P2P messenger.

Key exchange:  DH over RFC 3526 Group 14 (2048-bit MODP)
Encryption:    AES-CTR-like stream cipher using HMAC-SHA256 as PRF
Integrity:     HMAC-SHA256 over ciphertext (encrypt-then-MAC)
"""

import hashlib
import hmac
import secrets
import struct
from typing import Tuple, Optional


# RFC 3526 Group 14 -- 2048-bit MODP group
DH_PRIME = int(
    "FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD1"
    "29024E088A67CC74020BBEA63B139B22514A08798E3404DD"
    "EF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245"
    "E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7ED"
    "EE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3D"
    "C2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F"
    "83655D23DCA3AD961C62F356208552BB9ED529077096966D"
    "670C354E4ABC9804F1746C08CA18217C32905E462E36CE3B"
    "E39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9"
    "DE2BCBF6955817183995497CEA956AE515D2261898FA0510"
    "15728E5A8AACAA68FFFFFFFFFFFFFFFF",
    16,
)
DH_GENERATOR = 2

NONCE_SIZE = 16
MAC_SIZE = 32
KEY_SIZE = 32


class DHKeyPair:
    """Diffie-Hellman key pair for key exchange."""

    def __init__(self):
        self.private = secrets.randbelow(DH_PRIME - 2) + 2
        self.public = pow(DH_GENERATOR, self.private, DH_PRIME)

    def derive_shared(self, other_public: int) -> bytes:
        """Derive shared secret from peer's public key."""
        if not (2 <= other_public <= DH_PRIME - 2):
            raise ValueError("invalid public key")
        shared_int = pow(other_public, self.private, DH_PRIME)
        shared_bytes = shared_int.to_bytes(256, 'big')
        return hashlib.sha256(shared_bytes).digest()

    def public_bytes(self) -> bytes:
        """Serialize public key for transmission."""
        return self.public.to_bytes(256, 'big')

    @staticmethod
    def public_from_bytes(data: bytes) -> int:
        """Deserialize peer's public key."""
        return int.from_bytes(data, 'big')


def _hkdf_expand(key: bytes, info: bytes, length: int) -> bytes:
    """HKDF-Expand (RFC 5869) using HMAC-SHA256."""
    hash_len = 32
    n = (length + hash_len - 1) // hash_len
    okm = b""
    t = b""
    for i in range(1, n + 1):
        t = hmac.new(key, t + info + bytes([i]), hashlib.sha256).digest()
        okm += t
    return okm[:length]


def derive_keys(shared_secret: bytes) -> Tuple[bytes, bytes]:
    """Derive encryption key and MAC key from shared secret."""
    enc_key = _hkdf_expand(shared_secret, b"ttm2k-enc", KEY_SIZE)
    mac_key = _hkdf_expand(shared_secret, b"ttm2k-mac", KEY_SIZE)
    return enc_key, mac_key


def _keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    """Generate a keystream using HMAC-SHA256 in counter mode."""
    stream = b""
    counter = 0
    while len(stream) < length:
        block = hmac.new(
            key,
            nonce + struct.pack('>Q', counter),
            hashlib.sha256,
        ).digest()
        stream += block
        counter += 1
    return stream[:length]


def encrypt(plaintext: bytes, enc_key: bytes, mac_key: bytes) -> bytes:
    """
    Encrypt and authenticate a message.

    Returns: nonce (16) || ciphertext (len(plaintext)) || mac (32)
    """
    nonce = secrets.token_bytes(NONCE_SIZE)
    stream = _keystream(enc_key, nonce, len(plaintext))
    ciphertext = bytes(a ^ b for a, b in zip(plaintext, stream))
    mac = hmac.new(mac_key, nonce + ciphertext, hashlib.sha256).digest()
    return nonce + ciphertext + mac


def decrypt(
    data: bytes, enc_key: bytes, mac_key: bytes
) -> Optional[bytes]:
    """
    Verify and decrypt a message.

    Returns plaintext on success, None if MAC verification fails.
    """
    if len(data) < NONCE_SIZE + MAC_SIZE + 1:
        return None

    nonce = data[:NONCE_SIZE]
    ciphertext = data[NONCE_SIZE:-MAC_SIZE]
    received_mac = data[-MAC_SIZE:]

    expected_mac = hmac.new(
        mac_key, nonce + ciphertext, hashlib.sha256
    ).digest()
    if not hmac.compare_digest(received_mac, expected_mac):
        return None

    stream = _keystream(enc_key, nonce, len(ciphertext))
    plaintext = bytes(a ^ b for a, b in zip(ciphertext, stream))
    return plaintext


def hash_password(password: str, salt: Optional[bytes] = None) -> Tuple[bytes, bytes]:
    """Hash a password with PBKDF2-HMAC-SHA256."""
    if salt is None:
        salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100_000)
    return dk, salt


def verify_password(password: str, stored_hash: bytes, salt: bytes) -> bool:
    """Verify a password against a stored hash."""
    dk = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100_000)
    return hmac.compare_digest(dk, stored_hash)
