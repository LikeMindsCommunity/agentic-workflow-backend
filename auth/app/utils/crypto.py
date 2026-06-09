import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config.settings import settings


def _key() -> bytes:
    # MD5 of SECRET_KEY gives a 32-char hex string = 32 bytes, valid AES-256 key
    return hashlib.md5(settings.SECRET_KEY.encode()).hexdigest().encode()


def encrypt(plaintext: bytes) -> str:
    aesgcm = AESGCM(_key())
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return base64.b64encode(nonce + ciphertext).decode()


def decrypt(ciphertext_b64: str) -> bytes:
    raw = base64.b64decode(ciphertext_b64)
    nonce, ciphertext = raw[:12], raw[12:]
    aesgcm = AESGCM(_key())
    return aesgcm.decrypt(nonce, ciphertext, None)
