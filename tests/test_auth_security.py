"""
Characterization + edge-case tests for auth security primitives.

Coverage:
- security.py : hash_token, constant_time_equal, normalize_email, hash_ip,
                hash_email_for_log, create_csrf_token, verify_csrf_token
- deps.py     : origin_allowed
- auth_service: _mask_email

Run: pytest tests/test_auth_security.py -v
"""

from __future__ import annotations

import re

import pytest

from plantpal.auth_service import _mask_email
from plantpal.config import Settings
from plantpal.deps import origin_allowed
from plantpal.security import (
    constant_time_equal,
    create_csrf_token,
    hash_email_for_log,
    hash_ip,
    hash_token,
    normalize_email,
    verify_csrf_token,
)

# ---------------------------------------------------------------------------
# Helpers (mirrors the style in test_config.py)
# ---------------------------------------------------------------------------


def mk(**kw) -> Settings:
    """Build Settings ignoring any local .env so tests stay deterministic."""
    base: dict = {
        "_env_file": None,
        "APP_ENV": "test",
        "BASE_URL": "http://testserver",
        "TOKEN_PEPPER": "test-pepper",
        "CSRF_SECRET": "test-csrf",
        "RESEND_API_KEY": "",
    }
    base.update(kw)
    return Settings(**base)


def prod(**kw) -> Settings:
    """Build a production-like Settings (validate_runtime not called here)."""
    base: dict = {
        "_env_file": None,
        "APP_ENV": "production",
        "BASE_URL": "https://x.example",
        "TOKEN_PEPPER": "p" * 48,
        "CSRF_SECRET": "c" * 48,
        "RESEND_API_KEY": "re_x",
    }
    base.update(kw)
    return Settings(**base)


# Module-level settings instance reused across simple unit tests.
_S = mk()


# ===========================================================================
# hash_token
# ===========================================================================


class TestHashToken:
    def test_deterministic_for_same_token_and_pepper(self):
        h1 = hash_token("abc123", _S)
        h2 = hash_token("abc123", _S)
        assert h1 == h2

    def test_different_pepper_yields_different_hash(self):
        s1 = mk(TOKEN_PEPPER="pepper-one")
        s2 = mk(TOKEN_PEPPER="pepper-two")
        assert hash_token("same-token", s1) != hash_token("same-token", s2)

    def test_different_tokens_yield_different_hashes(self):
        assert hash_token("token-a", _S) != hash_token("token-b", _S)

    def test_output_is_full_length_hex(self):
        h = hash_token("any-token", _S)
        assert re.fullmatch(r"[0-9a-f]+", h), f"Expected hex, got: {h!r}"
        assert len(h) == 64  # SHA-256 → 64 hex chars


# ===========================================================================
# constant_time_equal
# ===========================================================================


class TestConstantTimeEqual:
    def test_equal_strings_return_true(self):
        assert constant_time_equal("hello", "hello") is True

    @pytest.mark.parametrize("b", ["helo", "Hello", "hello!", "", "HELLO"])
    def test_unequal_strings_return_false(self, b: str):
        assert constant_time_equal("hello", b) is False

    def test_different_length_returns_false(self):
        assert constant_time_equal("short", "much-longer-string") is False


# ===========================================================================
# normalize_email
# ===========================================================================


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Alice@Example.COM", "alice@example.com"),
        ("  user@domain.org  ", "user@domain.org"),
        ("\tBOB@EXAMPLE.NET\n", "bob@example.net"),
        ("already@lower.com", "already@lower.com"),
        ("UPPER@CAPS.IO", "upper@caps.io"),
        ("   Mixed@Case.De   ", "mixed@case.de"),
    ],
)
def test_normalize_email(raw: str, expected: str):
    assert normalize_email(raw) == expected


# ===========================================================================
# hash_ip
# ===========================================================================


class TestHashIp:
    def test_none_produces_stable_unknown_hash(self):
        h = hash_ip(None)
        assert len(h) == 32
        assert re.fullmatch(r"[0-9a-f]+", h)

    def test_empty_string_collapses_to_same_hash_as_none(self):
        # Both falsy values must map to "unknown" before hashing.
        assert hash_ip("") == hash_ip(None)

    def test_deterministic(self):
        assert hash_ip("192.168.1.1") == hash_ip("192.168.1.1")

    def test_output_length_is_32(self):
        assert len(hash_ip("10.0.0.1")) == 32

    def test_different_ips_produce_different_hashes(self):
        assert hash_ip("1.2.3.4") != hash_ip("4.3.2.1")

    def test_real_ip_differs_from_unknown_sentinel(self):
        assert hash_ip("127.0.0.1") != hash_ip(None)


# ===========================================================================
# hash_email_for_log
# ===========================================================================


class TestHashEmailForLog:
    def test_output_contains_no_at_sign(self):
        result = hash_email_for_log("user@example.com", _S)
        assert "@" not in result

    def test_output_length_is_12(self):
        result = hash_email_for_log("user@example.com", _S)
        assert len(result) == 12

    def test_keyed_by_pepper(self):
        s1 = mk(TOKEN_PEPPER="pepper-a")
        s2 = mk(TOKEN_PEPPER="pepper-b")
        h1 = hash_email_for_log("user@example.com", s1)
        h2 = hash_email_for_log("user@example.com", s2)
        assert h1 != h2

    def test_deterministic(self):
        h1 = hash_email_for_log("user@example.com", _S)
        h2 = hash_email_for_log("user@example.com", _S)
        assert h1 == h2


# ===========================================================================
# create_csrf_token + verify_csrf_token
# ===========================================================================


class TestCsrfToken:
    def test_valid_round_trip_returns_true(self):
        session = "my-session-token"
        csrf = create_csrf_token(session, _S)
        assert verify_csrf_token(csrf, csrf, session, _S) is True

    def test_header_not_equal_to_cookie_returns_false(self):
        # Two separate calls produce different nonces → different tokens.
        session = "my-session-token"
        t1 = create_csrf_token(session, _S)
        t2 = create_csrf_token(session, _S)
        # If by extreme coincidence t1 == t2 the test is vacuously useless;
        # in practice the 128-bit nonce makes collision essentially impossible.
        assert t1 != t2, "tokens should differ (different nonces)"
        assert verify_csrf_token(t1, t2, session, _S) is False

    def test_wrong_session_token_returns_false(self):
        session = "correct-session"
        csrf = create_csrf_token(session, _S)
        assert verify_csrf_token(csrf, csrf, "wrong-session", _S) is False

    def test_tampered_cookie_returns_false(self):
        session = "my-session-token"
        csrf = create_csrf_token(session, _S)
        # Flip the last character within the base64url alphabet.
        last = csrf[-1]
        replacement = "B" if last != "B" else "C"
        tampered = csrf[:-1] + replacement
        # header == cookie (both tampered), but HMAC must still fail.
        assert verify_csrf_token(tampered, tampered, session, _S) is False

    @pytest.mark.parametrize(
        "header, cookie, session",
        [
            (None, "some-token", "sess"),
            ("some-token", None, "sess"),
            ("some-token", "some-token", None),
            (None, None, None),
            ("", "some-token", "sess"),
            ("some-token", "", "sess"),
        ],
    )
    def test_missing_or_empty_arg_returns_false(
        self, header: str | None, cookie: str | None, session: str | None
    ):
        assert verify_csrf_token(header, cookie, session, _S) is False

    def test_emitted_token_uses_only_url_safe_chars_no_padding(self):
        # The double-b64e wrapping must produce only A-Za-z0-9_- (no = padding, no .).
        for _ in range(10):  # run several times to exercise different nonces
            csrf = create_csrf_token("any-session", _S)
            assert re.fullmatch(r"[A-Za-z0-9_-]+", csrf), (
                f"Token contains unexpected chars: {csrf!r}"
            )


# ===========================================================================
# origin_allowed
# ===========================================================================


class TestOriginAllowed:
    def test_exact_match_returns_true(self):
        s = mk(BASE_URL="http://testserver")
        assert origin_allowed("http://testserver", s) is True

    def test_none_candidate_returns_true(self):
        # No Origin/Referer header → fall back to double-submit check; never block here.
        s = mk(BASE_URL="http://testserver")
        assert origin_allowed(None, s) is True

    def test_empty_string_candidate_returns_true(self):
        # Empty string is falsy → same semantic as None.
        s = mk(BASE_URL="http://testserver")
        assert origin_allowed("", s) is True

    def test_port_mismatch_returns_false(self):
        s = mk(BASE_URL="http://testserver:8000")
        assert origin_allowed("http://testserver:9000", s) is False

    def test_scheme_mismatch_returns_false(self):
        s = prod(BASE_URL="https://x.example")
        assert origin_allowed("http://x.example", s) is False

    def test_subdomain_suffix_attack_rejected(self):
        # "https://x.example.evil.tld" must NOT match base "https://x.example".
        # A naive startswith/endswith check would wrongly accept this.
        s = prod(BASE_URL="https://x.example")
        assert origin_allowed("https://x.example.evil.tld", s) is False

    def test_dev_localhost_origin_allowed(self):
        s = mk(APP_ENV="test", BASE_URL="http://testserver")
        assert origin_allowed("http://localhost:5173", s) is True

    def test_dev_127001_origin_allowed(self):
        s = mk(APP_ENV="test", BASE_URL="http://testserver")
        assert origin_allowed("http://127.0.0.1:5173", s) is True

    def test_prod_non_base_origin_rejected(self):
        s = prod(BASE_URL="https://x.example")
        assert origin_allowed("https://attacker.example", s) is False

    def test_prod_localhost_origin_rejected(self):
        # In production the dev-localhost shortcut must NOT be active.
        s = prod(BASE_URL="https://x.example")
        assert origin_allowed("http://localhost:5173", s) is False


# ===========================================================================
# _mask_email
# ===========================================================================


class TestMaskEmail:
    @pytest.mark.parametrize(
        "email, first_char, domain",
        [
            ("alice@example.com", "a", "example.com"),
            ("bob@plantpal.app", "b", "plantpal.app"),
            ("zebra@long.subdomain.io", "z", "long.subdomain.io"),
        ],
    )
    def test_keeps_first_char_and_domain(self, email: str, first_char: str, domain: str):
        result = _mask_email(email)
        assert result.startswith(first_char + "***@")
        assert result.endswith("@" + domain)

    def test_empty_local_part_uses_question_mark_sentinel(self):
        # email = "@domain.com" → local part is empty → should not crash.
        result = _mask_email("@domain.com")
        assert result == "?***@domain.com"
