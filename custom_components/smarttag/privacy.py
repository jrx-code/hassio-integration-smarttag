"""Generowanie puli privacy ID SmartTaga.

Algorytm opisany na wiki uTag (strona BLE-Privacy-ID). Wejście pochodzi z pola
``bleD2D`` w opisie urządzenia z API SmartThings. Klucz ``encryptionKey`` jest
sekretem: nie logować go i nie zapisywać poza magazynem Home Assistant.
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


def _b64(value: str, urlsafe: bool = False) -> bytes:
    value = value.strip()
    value += "=" * (-len(value) % 4)
    if urlsafe:
        return base64.urlsafe_b64decode(value)
    return base64.b64decode(value)


def privacy_id_key(encryption_key: bytes) -> bytes:
    """SHA-256(key[:16] || be32(1) || b"privacy")[:16]."""
    digest = hashlib.sha256(encryption_key[:16] + (1).to_bytes(4, "big") + b"privacy").digest()
    return digest[:16]


def generate_pool(
    encryption_key_b64: str,
    pool_size: int,
    seed_b64: str,
    iv_b64: str,
) -> set[str]:
    """Zwraca zbiór privacy ID (16 znaków hex = 8 bajtów)."""
    key = privacy_id_key(_b64(encryption_key_b64, urlsafe=True))
    seed = _b64(seed_b64)
    iv = _b64(iv_b64)
    pool: set[str] = set()
    for index in range(pool_size):
        hi, lo = (index >> 8) & 0xFF, index & 0xFF
        block = bytes([hi, lo]) + seed + bytes([hi, lo])
        padder = padding.PKCS7(128).padder()
        padded = padder.update(block) + padder.finalize()
        encryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
        out = encryptor.update(padded) + encryptor.finalize()
        pool.add(out.hex()[:16])
    return pool


def pool_from_device(device: dict) -> set[str] | None:
    """Buduje pulę z odpowiedzi GET /devices/{id}. None, gdy brak danych."""
    ble = device.get("bleD2D") or {}
    meta = ble.get("metadata") or {}
    key = ble.get("encryptionKey")
    size = meta.get("privacyIdPoolSize")
    seed = meta.get("privacyIdSeed")
    iv = meta.get("privacyIdInitialVector")
    if not (key and size and seed and iv):
        return None
    return generate_pool(key, int(size), seed, iv)
