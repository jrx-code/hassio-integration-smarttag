import base64
import hashlib

import privacy
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

KEY = base64.urlsafe_b64encode(bytes(range(32))).decode()
SEED = base64.b64encode(bytes(range(100, 112))).decode()
IV = base64.b64encode(bytes(16)).decode()


def manual_entry(index: int) -> str:
    """Niezależne przeliczenie jednego wpisu (ręczny padding PKCS7)."""
    key = hashlib.sha256(bytes(range(16)) + b"\x00\x00\x00\x01privacy").digest()[:16]
    block = bytes([index >> 8, index & 0xFF]) + bytes(range(100, 112)) + bytes([index >> 8, index & 0xFF])
    pad = 16 - len(block) % 16
    block += bytes([pad]) * pad
    enc = Cipher(algorithms.AES(key), modes.CBC(bytes(16))).encryptor()
    return (enc.update(block) + enc.finalize()).hex()[:16]


def test_pool_size_and_format():
    pool = privacy.generate_pool(KEY, 300, SEED, IV)
    assert len(pool) == 300
    assert all(len(p) == 16 and int(p, 16) >= 0 for p in pool)


def test_pool_matches_manual_computation():
    pool = privacy.generate_pool(KEY, 300, SEED, IV)
    for index in (0, 1, 255, 256, 299):
        assert manual_entry(index) in pool


def test_pool_from_device_requires_all_fields():
    dev = {"bleD2D": {"encryptionKey": KEY, "metadata": {"privacyIdPoolSize": 5}}}
    assert privacy.pool_from_device(dev) is None
    dev["bleD2D"]["metadata"].update(privacyIdSeed=SEED, privacyIdInitialVector=IV)
    assert len(privacy.pool_from_device(dev)) == 5


def test_unpadded_base64_is_accepted():
    unpadded = KEY.rstrip("=")
    assert privacy.generate_pool(unpadded, 3, SEED, IV) == privacy.generate_pool(KEY, 3, SEED, IV)
