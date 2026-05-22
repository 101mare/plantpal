from datetime import datetime

from plantpal.time_utils import from_iso, now_berlin, parse_date, to_iso


def test_now_berlin_is_naive():
    assert now_berlin().tzinfo is None


def test_iso_roundtrip():
    dt = datetime(2026, 5, 21, 8, 30, 15)
    assert from_iso(to_iso(dt)) == dt


def test_from_iso_naive_is_passthrough():
    assert from_iso("2026-05-21T08:30:15.123456") == datetime(2026, 5, 21, 8, 30, 15)


def test_from_iso_converts_utc_to_berlin():
    # 23:30 UTC on 2026-05-21 is 01:30 Berlin on 2026-05-22 (CEST, +2h)
    assert from_iso("2026-05-21T23:30:00Z") == datetime(2026, 5, 22, 1, 30, 0)
    # explicit offset is converted too
    assert from_iso("2026-01-15T12:00:00+00:00") == datetime(2026, 1, 15, 13, 0, 0)  # CET +1h


def test_parse_date_handles_both_forms():
    assert parse_date("2026-05-21").isoformat() == "2026-05-21"
    assert parse_date("2026-05-21T09:00:00").isoformat() == "2026-05-21"
