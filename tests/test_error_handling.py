"""Validation errors must use the {error:{code,message}} contract, not FastAPI's {detail}.

Regression test for audit finding API-01: FastAPI's automatic body/query validation raises
``RequestValidationError`` (NOT ``pydantic.ValidationError``), which previously bypassed the
custom handler and reached the FE as an unreadable ``{detail: [...]}`` ("Unprocessable Entity").
"""


async def test_missing_required_field_uses_error_shape(client):
    # 'code' missing -> RequestValidationError regardless of field types
    r = await client.post("/auth/verify-code", json={"email": "u@b.c"})
    assert r.status_code == 422
    body = r.json()
    assert "detail" not in body  # not FastAPI's default shape
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["message"]  # human-readable, non-empty


async def test_invalid_email_uses_error_shape(client):
    r = await client.post("/auth/verify-code", json={"email": "not-an-email", "code": "123456"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"
