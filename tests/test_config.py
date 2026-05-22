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


def test_secure_cookies_for_https_dev():
    assert mk(APP_ENV="test", BASE_URL="https://local").secure_cookies is True
    assert mk(APP_ENV="test", BASE_URL="http://localhost:8000").secure_cookies is False
