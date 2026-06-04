import pytest

from plantpal import email_service as es
from plantpal.email_service import EmailUnavailableError


def test_build_magic_link():
    subject, html, text = es.build_magic_link("http://x/auth/verify?token=abc")
    assert "Login" in subject
    assert "auth/verify?token=abc" in html
    assert "auth/verify?token=abc" in text


def test_build_invite():
    subject, html, text = es.build_invite("http://x/register?token=abc")
    assert "plantpal" in subject.lower()
    assert "register?token=abc" in html
    assert "Familie" in html  # speaks in PlantPal's voice


def test_build_digest_pluralization():
    s1, _, _ = es.build_digest("http://x", [{"name": "Aloe", "days_overdue": 2}])
    assert "Eine von uns" in s1 and "hätte" in s1  # singular, PlantPal's voice
    s2, html2, text2 = es.build_digest(
        "http://x",
        [{"name": "Aloe", "days_overdue": 2}, {"name": "Fern", "days_overdue": 0}],
    )
    assert "2 von uns" in s2 and "hätten" in s2  # plural
    assert "Aloe" in html2 and "Fern" in text2


async def test_send_without_api_key_raises(settings):
    with pytest.raises(EmailUnavailableError):
        await es.send_magic_link(settings, "a@b.c", "http://x/verify")


async def test_send_success_with_mocked_http(settings, monkeypatch):
    s = settings.model_copy(update={"RESEND_API_KEY": "re_test"})

    class FakeResp:
        status_code = 200

        @staticmethod
        def json():
            return {"id": "email_1"}

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **k):
            return FakeResp()

    monkeypatch.setattr("plantpal.email_service.httpx.AsyncClient", FakeClient)
    result = await es.send_daily_digest(s, "a@b.c", [{"name": "X", "days_overdue": 1}])
    assert result == {"id": "email_1"}


def test_digest_escapes_plant_name():
    _, html, _ = es.build_digest(
        "http://x", [{"name": "<script>alert(1)</script>", "days_overdue": 1}]
    )
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


async def test_send_retries_on_429_then_succeeds(settings, monkeypatch):
    s = settings.model_copy(update={"RESEND_API_KEY": "re_test", "RESEND_MAX_RETRIES": 2})
    posts: list[int] = []
    queue = [429, 200]

    class FakeResp:
        def __init__(self, code):
            self.status_code = code
            self.text = "rate-limited"

        @staticmethod
        def json():
            return {"id": "ok"}

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **k):
            code = queue.pop(0)
            posts.append(code)
            return FakeResp(code)

    sleeps: list[float] = []

    async def fake_sleep(secs):
        sleeps.append(secs)

    monkeypatch.setattr("plantpal.email_service.httpx.AsyncClient", FakeClient)
    monkeypatch.setattr("plantpal.email_service.asyncio.sleep", fake_sleep)
    result = await es.send_magic_link(s, "a@b.c", "http://x/verify")
    assert result == {"id": "ok"}
    assert posts == [429, 200]  # retried once after the 429
    assert sleeps == [1]  # one exponential backoff (2**0)


async def test_send_http_error_raises(settings, monkeypatch):
    s = settings.model_copy(update={"RESEND_API_KEY": "re_test"})

    class FakeResp:
        status_code = 422
        text = "bad"

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **k):
            return FakeResp()

    monkeypatch.setattr("plantpal.email_service.httpx.AsyncClient", FakeClient)
    with pytest.raises(EmailUnavailableError, match="422"):
        await es.send_magic_link(s, "a@b.c", "http://x/verify")
