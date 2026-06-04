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
    # Brand tokens (BRAND.md §4): bg #0d2018, gold #e0b53d.
    return (
        '<div style="font-family:monospace;background:#0d2018;color:#e8f0e3;'
        'padding:24px;border-radius:12px;max-width:480px;margin:auto">'
        f'<h1 style="color:#e0b53d;font-size:20px">🌱 {title}</h1>{body_html}</div>'
    )


def _button(url: str, label: str) -> str:
    safe_url = escape(url, quote=True)
    return (
        f'<a href="{safe_url}" style="display:inline-block;background:#3a7d54;color:#fff;'
        'padding:12px 20px;border-radius:8px;text-decoration:none;margin-top:12px">'
        f"{escape(label)}</a>"
    )


def _code_block(code: str, hint: str) -> str:
    return (
        f'<p style="margin-top:16px">{escape(hint)}</p>'
        f'<p style="font-size:28px;letter-spacing:6px;font-family:monospace;color:#e0b53d">'
        f"<b>{escape(code)}</b></p>"
    )


def build_magic_link(url: str, code: str | None = None) -> tuple[str, str, str]:
    subject = "Dein PlantPal Login-Link"
    code_html = _code_block(code, "Oder gib diesen Code ein (10 Minuten gültig):") if code else ""
    html = _shell(
        "Schön, dass du da bist",
        f"<p>Klick zum Einloggen — der Link gilt 30 Minuten und nur einmal. "
        f"Deine Pflanzen freuen sich.</p>"
        f"{_button(url, 'Einloggen')}{code_html}",
    )
    code_text = f"\n\nOder Code eingeben (10 min gültig): {code}" if code else ""
    text = f"Dein PlantPal Login-Link (30 min gültig, einmalig):\n{url}{code_text}"
    return subject, html, text


def build_invite(url: str) -> tuple[str, str, str]:
    subject = "Komm zu PlantPal dazu 🌿"
    html = _shell(
        "Willkommen in der Familie",
        f"<p>Jemand möchte dich bei PlantPal dabeihaben. Leg einfach los — "
        f"deine erste Pflanze wartet schon auf dich.</p>"
        f"{_button(url, 'Account erstellen')}",
    )
    text = f"Jemand möchte dich bei PlantPal dabeihaben. Leg los:\n{url}"
    return subject, html, text


def build_digest(base_url: str, plants: list[dict]) -> tuple[str, str, str]:
    # Speaks AS PlantPal, not as a system report (BRAND.md §3, tone 2 — personal).
    n = len(plants)
    subject = (
        "🌱 Eine von uns hätte gern Wasser" if n == 1 else f"🌱 {n} von uns hätten gern Wasser"
    )

    def waited(days: int) -> str:
        if days <= 0:
            return "ist heute dran"
        return f"wartet seit {days} {'Tag' if days == 1 else 'Tagen'}"

    items_html = "".join(
        f"<li><b>{escape(str(p['name']))}</b> — {waited(int(p['days_overdue']))}</li>"
        for p in plants
    )
    html = _shell(
        "Kurzer Gruß von PlantPal",
        f"<p>Hey! Ein paar aus der Familie sind ein bisschen durstig:</p><ul>{items_html}</ul>"
        f"{_button(base_url, 'Schnell vorbeischauen')}",
    )
    lines = "\n".join(f"- {p['name']} ({waited(int(p['days_overdue']))})" for p in plants)
    text = f"Hey! Ein paar aus der Familie sind ein bisschen durstig:\n{lines}\n\n{base_url}"
    return subject, html, text


# --- Public send helpers ---


async def send_magic_link(settings: Settings, to: str, url: str, code: str | None = None) -> dict:
    return await _send(settings, to, *build_magic_link(url, code))


async def send_invite(settings: Settings, to: str, url: str) -> dict:
    return await _send(settings, to, *build_invite(url))


async def send_daily_digest(settings: Settings, to: str, plants: list[dict]) -> dict:
    return await _send(settings, to, *build_digest(settings.BASE_URL, plants))


# --- v3: email change (F-AUTH-29) ---


def build_email_change_verify(url: str, code: str) -> tuple[str, str, str]:
    subject = "Bestätige deine neue PlantPal-Email"
    html = _shell(
        "Email-Änderung bestätigen",
        f"<p>Bestätige deine neue Email-Adresse für PlantPal.</p>{_button(url, 'Bestätigen')}"
        + _code_block(code, "Oder gib diesen Code in PlantPal ein (30 Minuten gültig):"),
    )
    text = f"Bestätige deine neue PlantPal-Email:\n{url}\n\nOder Code (30 min gültig): {code}"
    return subject, html, text


def build_email_change_notice(new_email_masked: str) -> tuple[str, str, str]:
    subject = "Sicherheitshinweis: Email-Änderung beantragt"
    html = _shell(
        "Sicherheitshinweis",
        f"<p>Es wurde beantragt, deine PlantPal-Email zu <b>{escape(new_email_masked)}</b> zu "
        "ändern. Warst du das nicht, ignoriere diese Mail oder ändere deine Adresse zurück.</p>",
    )
    text = (
        f"Es wurde beantragt, deine PlantPal-Email zu {new_email_masked} zu ändern. "
        "Warst du das nicht, ignoriere diese Mail."
    )
    return subject, html, text


async def send_email_change_verify(settings: Settings, to: str, url: str, code: str) -> dict:
    return await _send(settings, to, *build_email_change_verify(url, code))


async def send_email_change_notice(settings: Settings, to: str, new_email_masked: str) -> dict:
    return await _send(settings, to, *build_email_change_notice(new_email_masked))
