"""Token generation/hashing, cookie helpers, CSRF, email/IP normalization."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

from .config import Settings


def new_url_token(nbytes: int = 32) -> str:
    """Cryptographically strong URL-safe random token (plaintext, given to user)."""
    return secrets.token_urlsafe(nbytes)


def hash_token(token: str, settings: Settings) -> str:
    """Deterministic keyed hash for DB storage. A leaked DB dump is not usable."""
    return hmac.new(settings.TOKEN_PEPPER.encode(), token.encode(), hashlib.sha256).hexdigest()


def constant_time_equal(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


def normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_ip(ip: str | None) -> str:
    """One-way hash of an IP for rate-limit keys / logs (no raw PII)."""
    if not ip:
        ip = "unknown"
    return hashlib.sha256(ip.encode()).hexdigest()[:32]


# --- CSRF: signed double-submit token bound to the session ---


def _b64e(data: bytes) -> str:
    """URL-safe base64 without ``=`` padding (so the value is cookie-safe)."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def create_csrf_token(session_token: str, settings: Settings) -> str:
    """HMAC over the session token + nonce; bound to the session, tamper-evident.

    Padding-free base64 keeps the value within ``[A-Za-z0-9-_.]`` so browsers and
    clients don't wrap it in quotes (which would break the header==cookie compare).
    """
    nonce = secrets.token_urlsafe(16)
    mac = hmac.new(
        settings.CSRF_SECRET.encode(), f"{session_token}:{nonce}".encode(), hashlib.sha256
    ).digest()
    raw = f"{nonce}.{_b64e(mac)}"
    return _b64e(raw.encode())


def verify_csrf_token(
    header_token: str | None,
    cookie_token: str | None,
    session_token: str | None,
    settings: Settings,
) -> bool:
    """Full double-submit check.

    1. Header value must equal the cookie value (constant-time) — a cross-site
       request cannot read the cookie to set the matching header.
    2. The cookie value's HMAC must bind to the current session token.
    """
    if not header_token or not cookie_token or not session_token:
        return False
    if not constant_time_equal(header_token, cookie_token):
        return False
    try:
        raw = _b64d(cookie_token).decode()
        nonce, mac_b64 = raw.split(".", 1)
        expected = hmac.new(
            settings.CSRF_SECRET.encode(), f"{session_token}:{nonce}".encode(), hashlib.sha256
        ).digest()
        return hmac.compare_digest(expected, _b64d(mac_b64))
    except (ValueError, TypeError):
        return False
