"""AK-LOG-3: email hashing for logs (no PII leak)."""

from plantpal.security import hash_email_for_log


def test_email_hash_no_pii(settings):
    h = hash_email_for_log("a@b.de", settings)
    assert "@" not in h
    assert h != "a@b.de"
    assert len(h) == 12
    assert hash_email_for_log("a@b.de", settings) == h  # deterministic
    assert hash_email_for_log("x@y.de", settings) != h  # different email -> different hash


def test_email_hash_case_insensitive(settings):
    assert hash_email_for_log("A@B.de", settings) == hash_email_for_log("a@b.de", settings)
