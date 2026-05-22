from plantpal.config import Settings
from plantpal.security import (
    create_csrf_token,
    hash_ip,
    hash_token,
    new_url_token,
    normalize_email,
    verify_csrf_token,
)

S = Settings(APP_ENV="test", TOKEN_PEPPER="pep", CSRF_SECRET="csrf")


def test_new_url_token_is_random_and_long():
    a, b = new_url_token(), new_url_token()
    assert a != b
    assert len(a) >= 32


def test_hash_token_is_deterministic_and_keyed():
    t = "abc"
    assert hash_token(t, S) == hash_token(t, S)
    other = Settings(APP_ENV="test", TOKEN_PEPPER="different", CSRF_SECRET="csrf")
    assert hash_token(t, S) != hash_token(t, other)
    assert hash_token(t, S) != t  # not plaintext


def test_normalize_email():
    assert normalize_email("  Foo@Bar.COM ") == "foo@bar.com"


def test_hash_ip_handles_none():
    assert hash_ip(None) == hash_ip(None)
    assert hash_ip("1.2.3.4") != hash_ip("1.2.3.5")


def test_csrf_roundtrip():
    session = new_url_token()
    token = create_csrf_token(session, S)
    # double-submit: header == cookie, both bind to session
    assert verify_csrf_token(token, token, session, S) is True


def test_csrf_rejects_header_cookie_mismatch():
    session = new_url_token()
    token = create_csrf_token(session, S)
    other = create_csrf_token(session, S)
    assert verify_csrf_token(other, token, session, S) is False


def test_csrf_rejects_wrong_session():
    token = create_csrf_token("session-a", S)
    assert verify_csrf_token(token, token, "session-b", S) is False


def test_csrf_rejects_garbage():
    assert verify_csrf_token("not-valid", "not-valid", "s", S) is False
    assert verify_csrf_token(None, None, "s", S) is False
    assert verify_csrf_token("x", "x", None, S) is False
