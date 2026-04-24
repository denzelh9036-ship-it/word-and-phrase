import hashlib
import os
import re
import secrets
from datetime import datetime, timedelta, timezone


PBKDF2_ITERS = 200_000
SESSION_DAYS = 30
USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,30}$")
MIN_PASSWORD_LEN = 6
COOKIE_NAME = "sessionid"


def hash_password(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    h = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERS
    )
    return h.hex(), salt.hex()


def verify_password(password, hash_hex, salt_hex):
    try:
        salt = bytes.fromhex(salt_hex)
    except ValueError:
        return False
    h = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERS
    )
    return secrets.compare_digest(h.hex(), hash_hex)


def new_session_token():
    return secrets.token_hex(32)


def session_expiry():
    return (datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)).isoformat()


def validate_username(username):
    if not username:
        return "Username required"
    if not USERNAME_RE.match(username):
        return "Username must be 3-30 characters (letters, digits, underscore)"
    return None


def validate_password(password):
    if not password or len(password) < MIN_PASSWORD_LEN:
        return f"Password must be at least {MIN_PASSWORD_LEN} characters"
    return None


def parse_cookie(cookie_header):
    if not cookie_header:
        return ""
    for part in cookie_header.split(";"):
        if "=" not in part:
            continue
        name, value = part.split("=", 1)
        if name.strip() == COOKIE_NAME:
            return value.strip()
    return ""


def _secure_flag():
    return "; Secure" if os.environ.get("COOKIE_SECURE") == "1" else ""


def set_cookie_header(token):
    max_age = SESSION_DAYS * 24 * 60 * 60
    return f"{COOKIE_NAME}={token}; Path=/; HttpOnly; Max-Age={max_age}; SameSite=Lax{_secure_flag()}"


def clear_cookie_header():
    return f"{COOKIE_NAME}=; Path=/; HttpOnly; Max-Age=0; SameSite=Lax{_secure_flag()}"
