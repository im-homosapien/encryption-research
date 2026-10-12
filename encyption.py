"""Handwritten notes catalog (advisor order). Homomorphic encryption is omitted.

1. Substitution — Caesar (``caesar_3``, ``caesar_7``)
2. Transposition — Columnar (``columnar``, key CRYPTO, pad X, order ``(key[i], i)``)
3. Stream — LFSR (``lfsr``)
4. Block — educational toy block (``toy_block``). This is **not** AES or DES.
5. DES / AES — modern block ciphers (``des``, ``aes``)
6. RSA — hybrid RSA-OAEP + AES session (``rsa``)

Dataset generation applies all six families. The 30-question pilot scores only (1) and (2).
See ``NOTES_CIPHERS`` below.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Callable, Protocol

from Crypto.Cipher import AES, DES, PKCS1_OAEP
from Crypto.PublicKey import RSA
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import pad, unpad

# Deterministic 1024-bit fixture key (research only — not an operational secret).
_RSA_PEM = """-----BEGIN PRIVATE KEY-----
MIICdgIBADANBgkqhkiG9w0BAQEFAASCAmAwggJcAgEAAoGBAKcV6rEM9JuII+vx
u66gWWuw0Re35ZPIQDRW4mXhf6BH0kBQsnUaYJGAeZmSfgbsv8bHH/hVZLWe8oDO
pGhcEbGPYxOrgQASi9RqlZRGF19DMk4uzi8jzStjhJ0tF5jgLaxhYpYHtBrxASpO
Ca5tDuPxBLs5Ngc29b3/URq1RGALAgMBAAECgYByHrwPdYPUfyXZz1+bJBYvQbNu
ecIqL8n6daVoZJ5hAO0P1I4vAXcXqiJjy/ScEjPiNrsVSG3ixs9nPrx4Mvo5q97s
5Oo7Hwddk2pkolXnmQOJLapi18jfZSNAeR18i/MdgvPsPsrwijDMDExiFv9sClQA
EU75GfABfcV2fx9KEQJBANKUmZmPntMnHqP5GqEQpIVOtSUsRW2LYIZ8eu5ZmKm4
ROL/kiBS7qJHDe8n4mlBcwlzfkmnsymeVyPARnUmj4cCQQDLH7UDLltrGKRfraqn
SblLl2IsPFl/SUoIuOcv6x2FU9MX2IxQBYWiTH8Ze8nGyDggW66IgKsvBVLx5jPt
ouRdAkA3y+ILG0/1GPd4cSfKJ5PAMsOyrtFSnkycNd2IzDq0Nbwi/Z7la7QJUZRy
mvnV896cUXrT31iMnYTvVyIUJnx/AkAHUIT8MFcqbCC/MUnL7GO3zSPD5Ah1BPad
icsJdrYBbxtS6IFlAE3nokmRaVvCxMMAp0yJrdh8QPzTqS6FiDAhAkEAz79/iSoo
BsJtc3ibPZc6Hvbgi4S8H8iSw2GRiKWi+r2XIzip0p4WpdDL8//S7XmkYs8ZOjyV
1Rmnsa85kKbmOw==
-----END PRIVATE KEY-----
"""

COLUMNAR_KEY = "CRYPTO"
COLUMNAR_PAD = "X"

# Documented pipeline keys — research fixtures, not operational secrets.
AES_KEY = b"CipherSolveAES16"  # 16 bytes
AES_IV = b"CipherSolveAESIV"  # 16 bytes
AES_KEY_HEX = AES_KEY.hex()

DES_KEY = b"CiphDES!"  # 8 bytes
DES_IV = b"DesIV!!!"  # 8 bytes
DES_KEY_HEX = DES_KEY.hex()

LFSR_SEED = 0xACE1
LFSR_TAPS = (0, 2, 3, 5)
LFSR_WIDTH = 16

TOY_BLOCK_KEY = b"TOYBLK!!"  # 8 bytes
TOY_BLOCK_SIZE = 8

def _load_rsa_key() -> RSA.RsaKey:
    return RSA.import_key(_RSA_PEM)


_RSA_KEY: RSA.RsaKey | None = None


def _rsa_key() -> RSA.RsaKey:
    """Lazy so Caesar/Columnar generation does not parse the fixture PEM."""
    global _RSA_KEY
    if _RSA_KEY is None:
        _RSA_KEY = _load_rsa_key()
    return _RSA_KEY


class CipherSpec(Protocol):
    name: str
    family: str
    description: str
    disclosed_blurb: str

    def encrypt(self, plaintext: str) -> str: ...

    def decrypt(self, ciphertext: str) -> str: ...


def caesar_encrypt(text: str, shift: int) -> str:
    """Shift A–Z / a–z by ``shift`` places. Non-letters are unchanged."""
    if shift % 26 == 0:
        return text
    out: list[str] = []
    for ch in text:
        if "A" <= ch <= "Z":
            out.append(chr((ord(ch) - 65 + shift) % 26 + 65))
        elif "a" <= ch <= "z":
            out.append(chr((ord(ch) - 97 + shift) % 26 + 97))
        else:
            out.append(ch)
    return "".join(out)


def caesar_decrypt(text: str, shift: int) -> str:
    return caesar_encrypt(text, -shift)


def _columnar_order(key: str) -> list[int]:
    return sorted(range(len(key)), key=lambda i: (key[i], i))


def columnar_encrypt(text: str, key: str = COLUMNAR_KEY, pad: str = COLUMNAR_PAD) -> str:
    """Write row-wise, read columns in ``(key[i], i)`` order, padding with X."""
    n_cols = len(key)
    if n_cols == 0:
        raise ValueError("columnar key must be non-empty")
    remainder = len(text) % n_cols
    padded = text + (pad * (n_cols - remainder) if remainder else "")
    n_rows = len(padded) // n_cols
    order = _columnar_order(key)
    return "".join(padded[row * n_cols + col] for col in order for row in range(n_rows))


def columnar_decrypt(ciphertext: str, key: str = COLUMNAR_KEY, pad: str = COLUMNAR_PAD) -> str:
    """Inverse of :func:`columnar_encrypt`. Trailing pad characters are stripped.

    ``rstrip(pad)`` can also remove a genuine trailing X in the original
    question. That does not occur in the GSM8K / SVAMP / MATH-500 items we
    ship, but it is a known limitation of this padding scheme.
    """
    n_cols = len(key)
    if n_cols == 0:
        raise ValueError("columnar key must be non-empty")
    if len(ciphertext) % n_cols != 0:
        raise ValueError(
            f"ciphertext length {len(ciphertext)} is not a multiple of key length {n_cols}"
        )
    n_rows = len(ciphertext) // n_cols
    order = _columnar_order(key)
    grid = [[""] * n_cols for _ in range(n_rows)]
    idx = 0
    for col in order:
        for row in range(n_rows):
            grid[row][col] = ciphertext[idx]
            idx += 1
    plaintext = "".join("".join(row) for row in grid)
    return plaintext.rstrip(pad)


class _LFSR:
    def __init__(self, seed: int, taps: tuple[int, ...], width: int) -> None:
        mask = (1 << width) - 1
        self.state = seed & mask
        if self.state == 0:
            self.state = 1
        self.taps = taps
        self.width = width
        self.mask = mask

    def bit(self) -> int:
        output = self.state & 1
        feedback = 0
        for tap in self.taps:
            feedback ^= (self.state >> tap) & 1
        self.state = ((self.state >> 1) | (feedback << (self.width - 1))) & self.mask
        return output

    def byte(self) -> int:
        value = 0
        for i in range(8):
            value |= self.bit() << i
        return value


def _lfsr_keystream(n: int, seed: int = LFSR_SEED) -> bytes:
    rng = _LFSR(seed, LFSR_TAPS, LFSR_WIDTH)
    return bytes(rng.byte() for _ in range(n))


def lfsr_encrypt(text: str, seed: int = LFSR_SEED) -> str:
    data = text.encode("utf-8")
    ks = _lfsr_keystream(len(data), seed)
    return bytes(a ^ b for a, b in zip(data, ks)).hex()


def lfsr_decrypt(ciphertext_hex: str, seed: int = LFSR_SEED) -> str:
    data = bytes.fromhex(ciphertext_hex)
    ks = _lfsr_keystream(len(data), seed)
    return bytes(a ^ b for a, b in zip(data, ks)).decode("utf-8")


def _toy_permute(block: bytearray, key: bytes) -> bytearray:
    order = sorted(range(TOY_BLOCK_SIZE), key=lambda i: (key[i], i))
    return bytearray(block[i] for i in order)


def _toy_unpermute(block: bytearray, key: bytes) -> bytearray:
    order = sorted(range(TOY_BLOCK_SIZE), key=lambda i: (key[i], i))
    out = bytearray(TOY_BLOCK_SIZE)
    for dest, src in enumerate(order):
        out[src] = block[dest]
    return out


def toy_block_encrypt(text: str, key: bytes = TOY_BLOCK_KEY) -> str:
    """Educational 8-byte ECB: XOR with key, then permute by ``(key[i], i)``."""
    if len(key) != TOY_BLOCK_SIZE:
        raise ValueError("toy block key must be 8 bytes")
    data = pad(text.encode("utf-8"), TOY_BLOCK_SIZE)
    out = bytearray()
    for i in range(0, len(data), TOY_BLOCK_SIZE):
        block = bytearray(data[i : i + TOY_BLOCK_SIZE])
        xored = bytearray(block[j] ^ key[j] for j in range(TOY_BLOCK_SIZE))
        out.extend(_toy_permute(xored, key))
    return bytes(out).hex()


def toy_block_decrypt(ciphertext_hex: str, key: bytes = TOY_BLOCK_KEY) -> str:
    data = bytes.fromhex(ciphertext_hex)
    if len(data) % TOY_BLOCK_SIZE != 0:
        raise ValueError("toy-block ciphertext is not block-aligned")
    out = bytearray()
    for i in range(0, len(data), TOY_BLOCK_SIZE):
        block = bytearray(data[i : i + TOY_BLOCK_SIZE])
        unperm = _toy_unpermute(block, key)
        out.extend(unperm[j] ^ key[j] for j in range(TOY_BLOCK_SIZE))
    return unpad(bytes(out), TOY_BLOCK_SIZE).decode("utf-8")


def aes_encrypt(text: str, key: bytes = AES_KEY, iv: bytes = AES_IV) -> str:
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return cipher.encrypt(pad(text.encode("utf-8"), AES.block_size)).hex()


def aes_decrypt(ciphertext_hex: str, key: bytes = AES_KEY, iv: bytes = AES_IV) -> str:
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return unpad(cipher.decrypt(bytes.fromhex(ciphertext_hex)), AES.block_size).decode("utf-8")


def des_encrypt(text: str, key: bytes = DES_KEY, iv: bytes = DES_IV) -> str:
    cipher = DES.new(key, DES.MODE_CBC, iv)
    return cipher.encrypt(pad(text.encode("utf-8"), DES.block_size)).hex()


def des_decrypt(ciphertext_hex: str, key: bytes = DES_KEY, iv: bytes = DES_IV) -> str:
    cipher = DES.new(key, DES.MODE_CBC, iv)
    return unpad(cipher.decrypt(bytes.fromhex(ciphertext_hex)), DES.block_size).decode("utf-8")


def rsa_encrypt(text: str, rsa_key: RSA.RsaKey | None = None) -> str:
    """Hybrid RSA-OAEP: wrap a random AES-128 session key, then AES-CBC the body.

    The session key and IV are generated per call, so ciphertext is not
    deterministic. Decrypt still round-trips. Format: ``rsa(session||iv) || aes(pt)``.
    """
    key = rsa_key or _rsa_key()
    session = get_random_bytes(16)
    iv = get_random_bytes(16)
    wrap = PKCS1_OAEP.new(key.publickey()).encrypt(session + iv)
    body = AES.new(session, AES.MODE_CBC, iv).encrypt(pad(text.encode("utf-8"), AES.block_size))
    return (wrap + body).hex()


def rsa_decrypt(ciphertext_hex: str, rsa_key: RSA.RsaKey | None = None) -> str:
    key = rsa_key or _rsa_key()
    blob = bytes.fromhex(ciphertext_hex)
    wrap_len = (key.size_in_bits() + 7) // 8
    wrap, body = blob[:wrap_len], blob[wrap_len:]
    session_iv = PKCS1_OAEP.new(key).decrypt(wrap)
    session, iv = session_iv[:16], session_iv[16:32]
    return unpad(AES.new(session, AES.MODE_CBC, iv).decrypt(body), AES.block_size).decode("utf-8")


class _NamedCipher:
    def __init__(
        self,
        name: str,
        family: str,
        description: str,
        disclosed_blurb: str,
        encrypt_fn: Callable[[str], str],
        decrypt_fn: Callable[[str], str],
        binary_payload: bool = False,
    ) -> None:
        self.name = name
        self.family = family
        self.description = description
        self.disclosed_blurb = disclosed_blurb
        self._encrypt = encrypt_fn
        self._decrypt = decrypt_fn
        self.binary_payload = binary_payload

    def encrypt(self, plaintext: str) -> str:
        return self._encrypt(plaintext)

    def decrypt(self, ciphertext: str) -> str:
        return self._decrypt(ciphertext)


def _caesar_blurb(shift: int) -> str:
    return (
        f"Caesar substitution cipher with shift {shift}. Each English letter is "
        f"moved {shift} places forward in the alphabet (wrapping from Z to A). "
        "Digits, punctuation, and whitespace are left unchanged. Decrypt by "
        f"shifting each letter backwards by {shift}."
    )


COLUMNAR_BLURB = (
    f"Columnar transposition with key {COLUMNAR_KEY}. Write the plaintext "
    f"row-wise into {len(COLUMNAR_KEY)} columns, pad the last row with "
    f"'{COLUMNAR_PAD}', then read columns in alphabetical order of the key "
    "letters, breaking ties by original column index (sort key is "
    f"(key[i], i)). Decrypt by reversing that permutation, then rstrip('{COLUMNAR_PAD}')."
)


CIPHERS: dict[str, _NamedCipher] = {
    "caesar_3": _NamedCipher(
        name="caesar_3",
        family="substitution",
        description="Caesar shift 3 (letter-only)",
        disclosed_blurb=_caesar_blurb(3),
        encrypt_fn=lambda t: caesar_encrypt(t, 3),
        decrypt_fn=lambda t: caesar_decrypt(t, 3),
    ),
    "caesar_7": _NamedCipher(
        name="caesar_7",
        family="substitution",
        description="Caesar shift 7 (letter-only)",
        disclosed_blurb=_caesar_blurb(7),
        encrypt_fn=lambda t: caesar_encrypt(t, 7),
        decrypt_fn=lambda t: caesar_decrypt(t, 7),
    ),
    "columnar": _NamedCipher(
        name="columnar",
        family="transposition",
        description=f"Columnar transposition, key {COLUMNAR_KEY}, pad {COLUMNAR_PAD}",
        disclosed_blurb=COLUMNAR_BLURB,
        encrypt_fn=lambda t: columnar_encrypt(t, COLUMNAR_KEY),
        decrypt_fn=lambda t: columnar_decrypt(t, COLUMNAR_KEY),
    ),
    "lfsr": _NamedCipher(
        name="lfsr",
        family="stream",
        description=f"16-bit LFSR stream cipher, seed 0x{LFSR_SEED:04X}, taps {LFSR_TAPS}",
        disclosed_blurb=(
            f"LFSR stream cipher (width {LFSR_WIDTH}, seed 0x{LFSR_SEED:04X}, "
            f"taps {LFSR_TAPS}). UTF-8 bytes are XOR-ed with the keystream; "
            "ciphertext is hex-encoded. Decrypt by XOR-ing the same keystream."
        ),
        encrypt_fn=lfsr_encrypt,
        decrypt_fn=lfsr_decrypt,
        binary_payload=True,
    ),
    "toy_block": _NamedCipher(
        name="toy_block",
        family="block",
        description="Educational toy 8-byte ECB block cipher (XOR + permutation). Not AES/DES.",
        disclosed_blurb=(
            "Educational toy 8-byte ECB block cipher — notes item 4, distinct from "
            "AES and DES. PKCS7-pad UTF-8 bytes, XOR each block with the 8-byte key "
            "TOYBLK!!, then permute bytes by (key[i], i). Ciphertext is hex. "
            "The undisclosed condition does not give the key."
        ),
        encrypt_fn=toy_block_encrypt,
        decrypt_fn=toy_block_decrypt,
        binary_payload=True,
    ),
    "des": _NamedCipher(
        name="des",
        family="modern_block",
        description="DES-CBC (pycryptodome), pipeline fixture key",
        disclosed_blurb=(
            "DES in CBC mode with PKCS7 padding and an 8-byte fixture key. "
            "Notes item 5 (modern block cipher, with AES). Ciphertext is hex. "
            "Too hard without the key; not the pilot default."
        ),
        encrypt_fn=des_encrypt,
        decrypt_fn=des_decrypt,
        binary_payload=True,
    ),
    "aes": _NamedCipher(
        name="aes",
        family="modern_block",
        description="AES-128-CBC (pycryptodome), pipeline fixture key",
        disclosed_blurb=(
            "AES-128 in CBC mode with PKCS7 padding. Notes item 5 (modern block "
            "cipher, with DES). The 16-byte key and IV are research fixtures. "
            "Ciphertext is hex. Too hard without the key; not the pilot default."
        ),
        encrypt_fn=aes_encrypt,
        decrypt_fn=aes_decrypt,
        binary_payload=True,
    ),
    "rsa": _NamedCipher(
        name="rsa",
        family="public_key",
        description="Hybrid RSA-OAEP + AES-128-CBC",
        disclosed_blurb=(
            "Notes item 6: hybrid RSA. A random AES-128 session key and IV are "
            "wrapped with RSA-OAEP (1024-bit fixture key, e=65537); the body is "
            "AES-CBC. Ciphertext is hex. Not the pilot default."
        ),
        encrypt_fn=rsa_encrypt,
        decrypt_fn=rsa_decrypt,
        binary_payload=True,
    ),
}

# Alias kept so older --ciphers block still hits notes item 4, not AES/DES.
CIPHERS["block"] = CIPHERS["toy_block"]

# Handwritten notes catalog, in advisor order. method_ids are --ciphers values.
NOTES_CIPHERS: tuple[dict[str, object], ...] = (
    {
        "notes_item": 1,
        "family": "substitution",
        "notes_name": "Substitution cipher — Caesar",
        "method_ids": ("caesar_3", "caesar_7"),
        "default_pilot": True,
        "enable": "default generate / --ciphers caesar_3 caesar_7",
    },
    {
        "notes_item": 2,
        "family": "transposition",
        "notes_name": "Transposition cipher — Columnar",
        "method_ids": ("columnar",),
        "default_pilot": True,
        "enable": "default generate / --ciphers columnar",
    },
    {
        "notes_item": 3,
        "family": "stream",
        "notes_name": "Stream cipher — LFSR",
        "method_ids": ("lfsr",),
        "default_pilot": False,
        "enable": "--ciphers lfsr",
    },
    {
        "notes_item": 4,
        "family": "block",
        "notes_name": "Block cipher",
        "method_ids": ("toy_block",),
        "default_pilot": False,
        "enable": "--ciphers toy_block",
    },
    {
        "notes_item": 5,
        "family": "modern_block",
        "notes_name": "DES / AES",
        "method_ids": ("des", "aes"),
        "default_pilot": False,
        "enable": "--ciphers des aes",
    },
    {
        "notes_item": 6,
        "family": "public_key",
        "notes_name": "RSA",
        "method_ids": ("rsa",),
        "default_pilot": False,
        "enable": "--ciphers rsa",
    },
)

# All method ids in notes order (Caesar's two shifts listed separately).
NOTES_METHOD_IDS: tuple[str, ...] = tuple(
    mid for item in NOTES_CIPHERS for mid in item["method_ids"]  # type: ignore[union-attr]
)

PILOT_CIPHERS = ("caesar_3", "caesar_7", "columnar")  # notes 1–2 only
HARD_CIPHERS = ("lfsr", "toy_block", "des", "aes", "rsa")  # notes 3–6

CIPHER_ALIASES = {
    "block": "toy_block",
    "toy-block": "toy_block",
    "toyblock": "toy_block",
    "transposition": "columnar",
    "stream": "lfsr",
    "substitution": "caesar_3",
    "caesar": "caesar_3",
}


def resolve_cipher_name(name: str) -> str:
    key = name.strip().lower().replace("-", "_")
    key = CIPHER_ALIASES.get(key, key)
    if key not in CIPHERS:
        known = ", ".join(NOTES_METHOD_IDS)
        raise KeyError(f"unknown cipher {name!r}. notes catalog ids: {known}")
    # Canonical name (so alias "block" reports as toy_block).
    return CIPHERS[key].name


def get_cipher(name: str) -> _NamedCipher:
    canonical = resolve_cipher_name(name)
    return CIPHERS[canonical]


def notes_label(cipher_id: str) -> str:
    """Human label matching the handwritten six-item list."""
    if cipher_id in {"none", "", "plaintext"}:
        return "plaintext (no cipher)"
    try:
        canonical = resolve_cipher_name(cipher_id)
    except KeyError:
        return str(cipher_id)
    for item in NOTES_CIPHERS:
        ids = item["method_ids"]
        assert isinstance(ids, tuple)
        if canonical in ids:
            n = item["notes_item"]
            return f"{n}. {item['notes_name']}"
    return canonical


def notes_catalog_help() -> str:
    lines = ["notes catalog (advisor order):"]
    for item in NOTES_CIPHERS:
        ids = " ".join(item["method_ids"])  # type: ignore[arg-type]
        flag = "default-pilot" if item["default_pilot"] else "opt-in"
        lines.append(f"  {item['notes_item']}. {item['notes_name']}  [{ids}] ({flag})")
    lines.append("No FHE.")
    return "\n".join(lines)


def verify_roundtrip(plaintext: str, cipher_name: str) -> bool:
    """Encrypt then decrypt; compare to the original.

    For columnar, compare against ``rstrip('X')`` of the original because
    decrypt always strips trailing pad characters.
    """
    canonical = resolve_cipher_name(cipher_name)
    cipher = get_cipher(canonical)
    recovered = cipher.decrypt(cipher.encrypt(plaintext))
    if canonical == "columnar":
        return recovered == plaintext.rstrip(COLUMNAR_PAD)
    return recovered == plaintext


def hmac_fingerprint(text: str) -> str:
    return hmac.new(b"ciphersolve-fp", text.encode("utf-8"), hashlib.sha256).hexdigest()[:16]


def assert_invariants() -> None:
    """Fail loudly if a pilot cipher is broken. Called before dataset generation."""
    samples = [
        "Hello, world!",
        "What is 2 + 2?",
        "Janet's ducks lay 16 eggs per day.",
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 $%().",
        "Convert the point $(0,3)$ in rectangular coordinates.",
    ]
    for text in samples:
        for shift in (3, 7):
            enc = caesar_encrypt(text, shift)
            dec = caesar_decrypt(enc, shift)
            if dec != text:
                raise AssertionError(
                    f"Caesar shift {shift} round-trip failed: {text!r} -> {enc!r} -> {dec!r}"
                )
        enc = columnar_encrypt(text)
        dec = columnar_decrypt(enc)
        if dec != text.rstrip(COLUMNAR_PAD):
            raise AssertionError(f"Columnar round-trip failed: {text!r} -> {enc!r} -> {dec!r}")
        if enc == text:
            raise AssertionError("Columnar produced unchanged plaintext")
        for name in NOTES_METHOD_IDS:
            if name.startswith("caesar") or name == "columnar":
                continue
            if not verify_roundtrip(text, name):
                raise AssertionError(f"{name} round-trip failed")
    # Known vector: HELLO + CRYPTO pad X → HXLEOL
    got = columnar_encrypt("HELLO", "CRYPTO")
    if got != "HXLEOL":
        raise AssertionError(f"Columnar known vector failed: {got!r}")
    if columnar_decrypt("HXLEOL", "CRYPTO") != "HELLO":
        raise AssertionError("Columnar known vector decrypt failed")
