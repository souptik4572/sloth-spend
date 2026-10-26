"""Password rules (the sign-up and reset designs) and hashing (stdlib scrypt, no extra dependency to bundle).

scrypt parameters follow an OWASP-listed profile (N=2^15, r=8, p=3: 32 MiB per hash). Every stored hash records
its own parameters, so they can be raised later without breaking existing accounts.
"""

import base64
import hashlib
import hmac
import os
import re
import secrets

N = int(os.environ.get("SLOTH_SCRYPT_N", str(2**15)))  # tests lower it; never lower it in production
R, P = 8, 3
KEY_BYTES = 32
MAX_LENGTH = 256

# The same three rules, in the same words, as the screens (web/src/lib/password.ts).
MIN_LENGTH = "At least 12 characters"
NUMBER_OR_SYMBOL = "A number or symbol"
NOT_EMAIL = "Doesn’t contain your email"
RULES = (MIN_LENGTH, NUMBER_OR_SYMBOL, NOT_EMAIL)


def problems(password: str, email: str) -> list[str]:
    """The rules this password breaks (empty = acceptable)."""
    out = []
    if len(password) < 12:
        out.append(MIN_LENGTH)
    if not re.search(r"[0-9\W_]", password):
        out.append(NUMBER_OR_SYMBOL)
    local = email.split("@", 1)[0].lower()
    if len(local) >= 3 and local in password.lower():
        out.append(NOT_EMAIL)
    if len(password) > MAX_LENGTH:
        out.append(f"At most {MAX_LENGTH} characters")
    return out


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode()


def _scrypt(password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(password.encode(), salt=salt, n=n, r=r, p=p, dklen=KEY_BYTES, maxmem=128 * r * n * 2 + 2**20)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    return f"scrypt${N}${R}${P}${_b64(salt)}${_b64(_scrypt(password, salt, N, R, P))}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, key = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = base64.b64decode(key)
        actual = _scrypt(password, base64.b64decode(salt), int(n), int(r), int(p))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


_dummy: str | None = None


def burn_time(password: str) -> None:
    """Hash against a throwaway when the email is unknown, so a login takes as long either way."""
    global _dummy
    if _dummy is None:
        _dummy = hash_password(secrets.token_urlsafe(16))
    verify_password(password, _dummy)
