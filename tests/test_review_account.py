"""Apple-Review-Account: fester Login-Code für GENAU eine konfigurierte E-Mail (2.1).

Pfad existiert nur, wenn REVIEW_ACCOUNT_EMAIL UND REVIEW_LOGIN_CODE gesetzt sind; falsche
Codes fallen in den normalen Token-Flow durch (generischer Fehler, keine Enumeration).
"""

from __future__ import annotations

import pytest

from plantpal import auth_service
from plantpal.errors import AppError


def _review_settings(settings, email="review@getplantpal.com", code="734291"):
    return settings.model_copy(
        update={"REVIEW_ACCOUNT_EMAIL": email, "REVIEW_LOGIN_CODE": code}
    )


async def test_review_code_opens_session_for_configured_account(db, settings):
    s = _review_settings(settings)
    await auth_service.bootstrap_admin(db, s, "review@getplantpal.com")
    raw, user = await auth_service.verify_login_code(db, s, "Review@GetPlantPal.com", "734291")
    assert user.email == "review@getplantpal.com"
    assert raw  # echte Session
    # Wiederholbar (nicht single-use — Apple testet mehrfach, auch nach Lösch-Tests anderer Flows)
    raw2, _ = await auth_service.verify_login_code(db, s, "review@getplantpal.com", "734291")
    assert raw2 and raw2 != raw


async def test_review_path_disabled_by_default(db, settings):
    await auth_service.bootstrap_admin(db, settings, "review@getplantpal.com")
    with pytest.raises(AppError):
        await auth_service.verify_login_code(db, settings, "review@getplantpal.com", "734291")


async def test_wrong_review_code_falls_through_generically(db, settings):
    s = _review_settings(settings)
    await auth_service.bootstrap_admin(db, s, "review@getplantpal.com")
    with pytest.raises(AppError) as exc:
        await auth_service.verify_login_code(db, s, "review@getplantpal.com", "000000")
    assert exc.value.code == "invalid_code"  # generisch, kein Review-Hinweis


async def test_review_code_requires_existing_active_user(db, settings):
    s = _review_settings(settings)  # Account NICHT angelegt
    with pytest.raises(AppError) as exc:
        await auth_service.verify_login_code(db, s, "review@getplantpal.com", "734291")
    assert exc.value.code == "invalid_code"


async def test_other_users_unaffected_by_review_config(db, settings):
    s = _review_settings(settings)
    await auth_service.bootstrap_admin(db, s, "normal@user.de")
    with pytest.raises(AppError):
        await auth_service.verify_login_code(db, s, "normal@user.de", "734291")
