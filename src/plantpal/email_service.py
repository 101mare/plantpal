"""Resend email integration with plaintext+HTML templates. Async via httpx.

Send failures raise EmailUnavailableError; callers (login route, reminder cron)
degrade gracefully — the CLI can always print a usable link instead.
"""

from __future__ import annotations

import asyncio
from html import escape

import httpx

from .config import Settings
from .errors import AppError

RESEND_ENDPOINT = "https://api.resend.com/emails"


class EmailUnavailableError(AppError):
    status_code = 502
    code = "email_unavailable"


async def _send(settings: Settings, to: str, subject: str, html: str, text: str) -> dict:
    """POST to Resend with exponential backoff on transient errors (429 / 5xx)."""
    if not settings.RESEND_API_KEY:
        raise EmailUnavailableError("Email provider not configured.")
    payload = {
        "from": settings.RESEND_FROM_EMAIL,
        "to": [to],
        "subject": subject,
        "html": html,
        "text": text,
    }
    last_error = "unknown error"
    for attempt in range(settings.RESEND_MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    RESEND_ENDPOINT,
                    headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
                    json=payload,
                )
        except httpx.HTTPError as exc:
            last_error = f"transport error: {exc}"
        else:
            if resp.status_code < 400:
                return resp.json()
            last_error = f"Resend error {resp.status_code}: {resp.text[:200]}"
            # Only 429 (rate limit) and 5xx are transient; 4xx is permanent.
            if resp.status_code != 429 and resp.status_code < 500:
                break
        if attempt < settings.RESEND_MAX_RETRIES:
            await asyncio.sleep(2**attempt)  # 1s, 2s, 4s …
    raise EmailUnavailableError(last_error)


# --- Templates ---


def _shell(title: str, body_html: str) -> str:
    return (
        '<div style="font-family:monospace;background:#1a3d2e;color:#e8f0e3;'
        'padding:24px;border-radius:12px;max-width:480px;margin:auto">'
        f'<h1 style="color:#d4af37;font-size:20px">🌱 {title}</h1>{body_html}</div>'
    )


def _button(url: str, label: str) -> str:
    safe_url = escape(url, quote=True)
    return (
        f'<a href="{safe_url}" style="display:inline-block;background:#3a7d54;color:#fff;'
        'padding:12px 20px;border-radius:8px;text-decoration:none;margin-top:12px">'
        f"{escape(label)}</a>"
    )


def build_magic_link(url: str) -> tuple[str, str, str]:
    subject = "Dein PlantPal Login-Link"
    html = _shell(
        "PlantPal Login",
        f"<p>Klicke zum Einloggen. Der Link ist 30 Minuten gültig und einmalig nutzbar.</p>"
        f"{_button(url, 'Einloggen')}",
    )
    text = f"PlantPal Login (30 min gültig, einmalig):\n{url}"
    return subject, html, text


def build_invite(url: str) -> tuple[str, str, str]:
    subject = "Du bist zu PlantPal eingeladen 🌿"
    html = _shell(
        "Einladung",
        f"<p>Du wurdest zu PlantPal eingeladen. Erstelle deinen Account:</p>"
        f"{_button(url, 'Account erstellen')}",
    )
    text = f"Du bist zu PlantPal eingeladen. Account erstellen:\n{url}"
    return subject, html, text


def build_digest(base_url: str, plants: list[dict]) -> tuple[str, str, str]:
    n = len(plants)
    subject = f"🌱 {n} Pflanze{'n' if n != 1 else ''} {'haben' if n != 1 else 'hat'} Durst"
    items_html = "".join(
        f"<li><b>{escape(str(p['name']))}</b> — {int(p['days_overdue'])} Tag(e) überfällig</li>"
        for p in plants
    )
    html = _shell(
        "Gieß-Erinnerung",
        f"<p>Diese Pflanzen brauchen Wasser:</p><ul>{items_html}</ul>"
        f"{_button(base_url, 'Zu PlantPal')}",
    )
    lines = "\n".join(f"- {p['name']} ({p['days_overdue']}d überfällig)" for p in plants)
    text = f"Diese Pflanzen brauchen Wasser:\n{lines}\n\n{base_url}"
    return subject, html, text


# --- Public send helpers ---


async def send_magic_link(settings: Settings, to: str, url: str) -> dict:
    return await _send(settings, to, *build_magic_link(url))


async def send_invite(settings: Settings, to: str, url: str) -> dict:
    return await _send(settings, to, *build_invite(url))


async def send_daily_digest(settings: Settings, to: str, plants: list[dict]) -> dict:
    return await _send(settings, to, *build_digest(settings.BASE_URL, plants))
