import pytest

from plantpal.config import Settings


def mk(**kw) -> Settings:
    """Build Settings ignoring any local .env so tests are deterministic."""
    return Settings(_env_file=None, **kw)


def test_defaults_are_sane():
    s = mk(APP_ENV="test")
    assert s.SESSION_SOFT_CAP_DAYS == 90
    assert s.SESSION_HARD_CAP_DAYS == 180
    assert s.LOGIN_TOKEN_TTL_MIN == 30
    assert s.IMG_SIZE_PX == 96


def test_validate_runtime_rejects_inverted_caps():
    s = mk(APP_ENV="test", SESSION_SOFT_CAP_DAYS=200, SESSION_HARD_CAP_DAYS=100)
    with pytest.raises(ValueError, match="HARD_CAP"):
        s.validate_runtime()


def test_validate_runtime_requires_secrets_in_prod():
    s = mk(APP_ENV="production", BASE_URL="https://x.example", RESEND_API_KEY="re_x")
    with pytest.raises(ValueError, match="TOKEN_PEPPER"):
        s.validate_runtime()


def test_validate_runtime_requires_resend_in_prod():
    s = mk(
        APP_ENV="production",
        BASE_URL="https://x.example",
        TOKEN_PEPPER="x" * 48,
        CSRF_SECRET="y" * 48,
        RESEND_API_KEY="",
    )
    with pytest.raises(ValueError, match="RESEND_API_KEY"):
        s.validate_runtime()


def test_validate_runtime_rejects_short_secrets_in_prod():
    s = mk(
        APP_ENV="production",
        BASE_URL="https://x.example",
        TOKEN_PEPPER="short",
        CSRF_SECRET="y" * 48,
        RESEND_API_KEY="re_x",
    )
    with pytest.raises(ValueError, match="TOKEN_PEPPER"):
        s.validate_runtime()


def test_validate_runtime_rejects_localhost_in_prod():
    s = mk(APP_ENV="production", BASE_URL="https://localhost:8000")
    with pytest.raises(ValueError, match="localhost"):
        s.validate_runtime()


def _prod(**kw) -> Settings:
    """A production Settings that passes all checks except the one under test."""
    base = {
        "APP_ENV": "production",
        "BASE_URL": "https://x.example",
        "TOKEN_PEPPER": "p" * 48,
        "CSRF_SECRET": "c" * 48,
        "RESEND_API_KEY": "re_x",
        "RESEND_FROM_EMAIL": "PlantPal <noreply@x.example>",
    }
    base.update(kw)
    return mk(**base)


def test_validate_runtime_rejects_localhost_from_email_in_prod():
    s = _prod(RESEND_FROM_EMAIL="PlantPal <noreply@localhost>")
    with pytest.raises(ValueError, match="RESEND_FROM_EMAIL"):
        s.validate_runtime()


def test_validate_runtime_rejects_from_email_without_at_in_prod():
    s = _prod(RESEND_FROM_EMAIL="noreply")
    with pytest.raises(ValueError, match="RESEND_FROM_EMAIL"):
        s.validate_runtime()


@pytest.mark.parametrize(
    "from_email",
    [
        "PlantPal <onboarding@resend.dev>",  # Resend sandbox: only delivers to account owner (N19)
        "noreply@resend.dev",
        "PlantPal <noreply@example.com>",  # placeholder domains never deliver
        "noreply@example.org",
    ],
)
def test_validate_runtime_rejects_sandbox_and_placeholder_from_email_in_prod(from_email):
    s = _prod(RESEND_FROM_EMAIL=from_email)
    with pytest.raises(ValueError, match="RESEND_FROM_EMAIL"):
        s.validate_runtime()


def test_validate_runtime_requires_replica_url_when_litestream_on():
    s = _prod(LITESTREAM_ENABLED=True, LITESTREAM_REPLICA_URL=None)
    with pytest.raises(ValueError, match="LITESTREAM_REPLICA_URL"):
        s.validate_runtime()


def test_validate_runtime_accepts_full_valid_prod_config():
    _prod(LITESTREAM_ENABLED=True, LITESTREAM_REPLICA_URL="s3://bucket/db").validate_runtime()


def test_secure_cookies_for_https_dev():
    assert mk(APP_ENV="test", BASE_URL="https://local").secure_cookies is True
    assert mk(APP_ENV="test", BASE_URL="http://localhost:8000").secure_cookies is False
