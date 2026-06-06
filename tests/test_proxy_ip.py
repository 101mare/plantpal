"""C4: real client IP behind the Cloudflare Tunnel (CF-Connecting-IP), F-DEP-7.

Without this, request.client.host is always the cloudflared container, so every
visitor shares one rate-limit bucket and a single attacker can lock everyone out.
"""

from __future__ import annotations

import types

from starlette.requests import Request

from plantpal.config import Settings
from plantpal.deps import client_ip
from plantpal.security import hash_ip


def mk(**kw) -> Settings:
    return Settings(_env_file=None, APP_ENV="test", **kw)


def _request(settings: Settings, *, cf: str | None, peer: str = "10.0.0.1") -> Request:
    app = types.SimpleNamespace(state=types.SimpleNamespace(settings=settings))
    headers = [(b"cf-connecting-ip", cf.encode())] if cf is not None else []
    scope = {"type": "http", "headers": headers, "client": (peer, 12345), "app": app}
    return Request(scope)


def test_prefers_cf_header_when_trusted():
    r = _request(mk(TRUST_CF_CONNECTING_IP=True), cf="203.0.113.5", peer="10.0.0.1")
    assert client_ip(r) == hash_ip("203.0.113.5")


def test_ignores_cf_header_when_distrusted():
    r = _request(mk(TRUST_CF_CONNECTING_IP=False), cf="203.0.113.5", peer="10.0.0.1")
    assert client_ip(r) == hash_ip("10.0.0.1")


def test_falls_back_to_peer_without_cf_header():
    r = _request(mk(TRUST_CF_CONNECTING_IP=True), cf=None, peer="10.0.0.1")
    assert client_ip(r) == hash_ip("10.0.0.1")


def test_strips_whitespace_in_cf_header():
    r = _request(mk(TRUST_CF_CONNECTING_IP=True), cf="  203.0.113.9  ")
    assert client_ip(r) == hash_ip("203.0.113.9")


async def test_distinct_cf_ips_get_distinct_buckets(client):
    """End-to-end: the per-IP register limit (10/h) must not collapse across CF IPs."""
    for i in range(12):  # well past the 10/h IP limit
        r = await client.post(
            "/auth/register",
            json={"invite_token": "invalid-but-long-enough", "email": f"u{i}@example.de"},
            headers={"cf-connecting-ip": f"203.0.113.{i}"},
        )
        assert r.status_code != 429, f"distinct CF IP #{i} should have its own bucket"


async def test_same_cf_ip_shares_one_bucket(client):
    last = None
    for i in range(12):
        last = await client.post(
            "/auth/register",
            json={"invite_token": "invalid-but-long-enough", "email": f"u{i}@example.de"},
            headers={"cf-connecting-ip": "203.0.113.50"},
        )
    assert last.status_code == 429  # 11th request trips the 10/h IP limit
