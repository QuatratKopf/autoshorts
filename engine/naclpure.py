"""NaCl-kompatible Verschlüsselung in reinem Python (ohne Zusatzpakete).

- sealed_box(msg, public_key)      wie libsodium crypto_box_seal (für GitHub-Secrets)
- secretbox / secretbox_open        wie crypto_secretbox (für die gespeicherten Anmeldungen)

Langsam, aber für kurze Texte (Schlüssel, Tokens) mehr als schnell genug.
"""
import hashlib
import os
import struct

# ---------------------------------------------------------------- X25519 (RFC 7748)
_P = 2 ** 255 - 19
_A24 = 121665


def _clamp(k):
    k = bytearray(k)
    k[0] &= 248
    k[31] &= 127
    k[31] |= 64
    return int.from_bytes(k, "little")


def x25519(scalar: bytes, u: bytes) -> bytes:
    k = _clamp(scalar)
    x1 = int.from_bytes(u, "little") & ((1 << 255) - 1)
    x2, z2, x3, z3, swap = 1, 0, x1, 1, 0
    for t in reversed(range(255)):
        kt = (k >> t) & 1
        swap ^= kt
        if swap:
            x2, x3, z2, z3 = x3, x2, z3, z2
        swap = kt
        a, b = (x2 + z2) % _P, (x2 - z2) % _P
        aa, bb = a * a % _P, b * b % _P
        e = (aa - bb) % _P
        c, d = (x3 + z3) % _P, (x3 - z3) % _P
        da, cb = d * a % _P, c * b % _P
        x3 = (da + cb) ** 2 % _P
        z3 = x1 * (da - cb) ** 2 % _P
        x2 = aa * bb % _P
        z2 = e * (aa + _A24 * e) % _P
    if swap:
        x2, z2 = x3, z3
    return (x2 * pow(z2, _P - 2, _P) % _P).to_bytes(32, "little")


def x25519_base(scalar: bytes) -> bytes:
    return x25519(scalar, (9).to_bytes(32, "little"))


# ---------------------------------------------------------------- Salsa20 / HSalsa20 / XSalsa20

def _rotl(v, c):
    return ((v << c) & 0xFFFFFFFF) | (v >> (32 - c))


def _rounds(x):
    for _ in range(10):
        # Spalten
        x[4] ^= _rotl((x[0] + x[12]) & 0xFFFFFFFF, 7); x[8] ^= _rotl((x[4] + x[0]) & 0xFFFFFFFF, 9)
        x[12] ^= _rotl((x[8] + x[4]) & 0xFFFFFFFF, 13); x[0] ^= _rotl((x[12] + x[8]) & 0xFFFFFFFF, 18)
        x[9] ^= _rotl((x[5] + x[1]) & 0xFFFFFFFF, 7); x[13] ^= _rotl((x[9] + x[5]) & 0xFFFFFFFF, 9)
        x[1] ^= _rotl((x[13] + x[9]) & 0xFFFFFFFF, 13); x[5] ^= _rotl((x[1] + x[13]) & 0xFFFFFFFF, 18)
        x[14] ^= _rotl((x[10] + x[6]) & 0xFFFFFFFF, 7); x[2] ^= _rotl((x[14] + x[10]) & 0xFFFFFFFF, 9)
        x[6] ^= _rotl((x[2] + x[14]) & 0xFFFFFFFF, 13); x[10] ^= _rotl((x[6] + x[2]) & 0xFFFFFFFF, 18)
        x[3] ^= _rotl((x[15] + x[11]) & 0xFFFFFFFF, 7); x[7] ^= _rotl((x[3] + x[15]) & 0xFFFFFFFF, 9)
        x[11] ^= _rotl((x[7] + x[3]) & 0xFFFFFFFF, 13); x[15] ^= _rotl((x[11] + x[7]) & 0xFFFFFFFF, 18)
        # Zeilen
        x[1] ^= _rotl((x[0] + x[3]) & 0xFFFFFFFF, 7); x[2] ^= _rotl((x[1] + x[0]) & 0xFFFFFFFF, 9)
        x[3] ^= _rotl((x[2] + x[1]) & 0xFFFFFFFF, 13); x[0] ^= _rotl((x[3] + x[2]) & 0xFFFFFFFF, 18)
        x[6] ^= _rotl((x[5] + x[4]) & 0xFFFFFFFF, 7); x[7] ^= _rotl((x[6] + x[5]) & 0xFFFFFFFF, 9)
        x[4] ^= _rotl((x[7] + x[6]) & 0xFFFFFFFF, 13); x[5] ^= _rotl((x[4] + x[7]) & 0xFFFFFFFF, 18)
        x[11] ^= _rotl((x[10] + x[9]) & 0xFFFFFFFF, 7); x[8] ^= _rotl((x[11] + x[10]) & 0xFFFFFFFF, 9)
        x[9] ^= _rotl((x[8] + x[11]) & 0xFFFFFFFF, 13); x[10] ^= _rotl((x[9] + x[8]) & 0xFFFFFFFF, 18)
        x[12] ^= _rotl((x[15] + x[14]) & 0xFFFFFFFF, 7); x[13] ^= _rotl((x[12] + x[15]) & 0xFFFFFFFF, 9)
        x[14] ^= _rotl((x[13] + x[12]) & 0xFFFFFFFF, 13); x[15] ^= _rotl((x[14] + x[13]) & 0xFFFFFFFF, 18)
    return x


_SIGMA = struct.unpack("<4I", b"expand 32-byte k")


def _state(key, inp16):
    k = struct.unpack("<8I", key)
    n = struct.unpack("<4I", inp16)
    return [_SIGMA[0], k[0], k[1], k[2], k[3], _SIGMA[1], n[0], n[1], n[2], n[3], _SIGMA[2],
            k[4], k[5], k[6], k[7], _SIGMA[3]]


def hsalsa20(key: bytes, inp16: bytes) -> bytes:
    x = _rounds(_state(key, inp16))
    return struct.pack("<8I", x[0], x[5], x[10], x[15], x[6], x[7], x[8], x[9])


def _salsa20_block(key, nonce8, counter):
    s = _state(key, nonce8 + struct.pack("<Q", counter))
    x = _rounds(list(s))
    return struct.pack("<16I", *((x[i] + s[i]) & 0xFFFFFFFF for i in range(16)))


def xsalsa20_xor(msg: bytes, nonce24: bytes, key: bytes) -> bytes:
    subkey = hsalsa20(key, nonce24[:16])
    n8 = nonce24[16:24]
    out = bytearray(len(msg))
    for blk in range((len(msg) + 63) // 64):
        ks = _salsa20_block(subkey, n8, blk)
        off = blk * 64
        chunk = msg[off:off + 64]
        for i, b in enumerate(chunk):
            out[off + i] = b ^ ks[i]
    return bytes(out)


# ---------------------------------------------------------------- Poly1305

def poly1305(msg: bytes, key: bytes) -> bytes:
    r = int.from_bytes(key[:16], "little") & 0x0FFFFFFC0FFFFFFC0FFFFFFC0FFFFFFF
    s = int.from_bytes(key[16:32], "little")
    p = (1 << 130) - 5
    acc = 0
    for i in range(0, len(msg), 16):
        n = int.from_bytes(msg[i:i + 16] + b"\x01", "little")
        acc = (acc + n) * r % p
    return ((acc + s) & ((1 << 128) - 1)).to_bytes(16, "little")


# ---------------------------------------------------------------- secretbox (XSalsa20-Poly1305)

def secretbox(msg: bytes, nonce24: bytes, key: bytes) -> bytes:
    """Gibt MAC (16 Byte) + Geheimtext zurück, wie libsodium crypto_secretbox_easy."""
    stream = xsalsa20_xor(b"\x00" * 32 + msg, nonce24, key)
    ct = stream[32:]
    return poly1305(ct, stream[:32]) + ct


def secretbox_open(box: bytes, nonce24: bytes, key: bytes) -> bytes:
    mac, ct = box[:16], box[16:]
    otk = xsalsa20_xor(b"\x00" * 32, nonce24, key)
    if not _eq(poly1305(ct, otk), mac):
        raise ValueError("Entschlüsselung fehlgeschlagen")
    return xsalsa20_xor(b"\x00" * 32 + ct, nonce24, key)[32:]


def _eq(a, b):
    if len(a) != len(b):
        return False
    r = 0
    for x, y in zip(a, b):
        r |= x ^ y
    return r == 0


# ---------------------------------------------------------------- box / sealed box

def box_beforenm(public_key: bytes, secret_key: bytes) -> bytes:
    return hsalsa20(x25519(secret_key, public_key), b"\x00" * 16)


def sealed_box(msg: bytes, public_key: bytes) -> bytes:
    """crypto_box_seal: ephemeral_pk || box(msg) mit nonce = blake2b(epk || pk, 24)."""
    esk = os.urandom(32)
    epk = x25519_base(esk)
    nonce = hashlib.blake2b(epk + public_key, digest_size=24).digest()
    return epk + secretbox(msg, nonce, box_beforenm(public_key, esk))


# ---------------------------------------------------------------- einfache Ver-/Entschlüsselung mit Passwort-Ableitung

def derive_key(*parts: str) -> bytes:
    return hashlib.sha256(":".join(parts).encode()).digest()


def encrypt(data: bytes, key: bytes) -> bytes:
    nonce = os.urandom(24)
    return b"AS1" + nonce + secretbox(data, nonce, key)


def decrypt(blob: bytes, key: bytes) -> bytes:
    if not blob.startswith(b"AS1"):
        raise ValueError("Unbekanntes Format")
    return secretbox_open(blob[27:], blob[3:27], key)
