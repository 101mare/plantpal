import aiosqlite
import pytest

from plantpal.errors import RateLimitError
from plantpal.rate_limit import check_rate_limit, key_email, parse_rule


def test_parse_rule():
    assert parse_rule("3/h") == (3, 3600)
    assert parse_rule("30/m") == (30, 60)
    assert parse_rule("10/s") == (10, 1)  # 10 per 1 second
    assert parse_rule("5/2m") == (5, 120)


def test_parse_rule_bad_unit():
    with pytest.raises(ValueError, match="unit"):
        parse_rule("3/x")


async def test_under_limit_passes(db: aiosqlite.Connection):
    key = key_email("a@b.c", "login")
    for _ in range(3):
        await check_rate_limit(db, key, "3/h")  # 3 allowed


async def test_over_limit_raises(db: aiosqlite.Connection):
    key = key_email("a@b.c", "login")
    for _ in range(3):
        await check_rate_limit(db, key, "3/h")
    with pytest.raises(RateLimitError) as exc:
        await check_rate_limit(db, key, "3/h")  # 4th over limit
    assert exc.value.retry_after > 0


async def test_distinct_keys_independent(db: aiosqlite.Connection):
    await check_rate_limit(db, key_email("a@b.c", "login"), "1/h")
    # different email, fresh window
    await check_rate_limit(db, key_email("c@d.e", "login"), "1/h")
