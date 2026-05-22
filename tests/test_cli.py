"""CLI tests. Each command runs through ``main()`` against a tmp DB via env override."""

from plantpal.cli import main
from plantpal.config import Settings, get_settings


def _patch_settings(monkeypatch, tmp_path):
    s = Settings(
        APP_ENV="test",
        BASE_URL="http://testserver",
        DB_PATH=str(tmp_path / "cli.db"),
        IMAGE_DIR=str(tmp_path / "img"),
        TOKEN_PEPPER="t",
        CSRF_SECRET="c",
        RESEND_API_KEY="",
    )
    get_settings.cache_clear()
    monkeypatch.setattr("plantpal.cli.get_settings", lambda: s)
    return s


def test_bootstrap_admin_cli(monkeypatch, tmp_path, capsys):
    _patch_settings(monkeypatch, tmp_path)
    rc = main(["bootstrap-admin", "--email", "admin@b.c"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Login link:" in out
    assert "/auth/verify?token=" in out


def test_create_invite_requires_admin(monkeypatch, tmp_path):
    _patch_settings(monkeypatch, tmp_path)
    # no admin yet → created-by lookup fails
    rc = main(["create-invite", "--created-by", "ghost@b.c"])
    assert rc == 1


def test_create_invite_system_cli(monkeypatch, tmp_path, capsys):
    _patch_settings(monkeypatch, tmp_path)
    rc = main(["create-invite"])  # no created-by → system invite
    assert rc == 0
    assert "/register?token=" in capsys.readouterr().out


def test_issue_login_link_unknown_user(monkeypatch, tmp_path):
    _patch_settings(monkeypatch, tmp_path)
    rc = main(["issue-login-link", "--email", "nobody@b.c"])
    assert rc == 1


def test_issue_login_link_for_existing(monkeypatch, tmp_path, capsys):
    _patch_settings(monkeypatch, tmp_path)
    main(["bootstrap-admin", "--email", "admin@b.c"])
    capsys.readouterr()  # drain
    rc = main(["issue-login-link", "--email", "admin@b.c"])
    assert rc == 0
    assert "/auth/verify?token=" in capsys.readouterr().out


def test_bootstrap_force_allows_second_cli(monkeypatch, tmp_path):
    _patch_settings(monkeypatch, tmp_path)
    assert main(["bootstrap-admin", "--email", "a@b.c"]) == 0
    assert main(["bootstrap-admin", "--email", "b@b.c"]) == 1  # ConflictError → AppError → rc 1
    assert main(["bootstrap-admin", "--email", "b@b.c", "--force"]) == 0


def test_create_invite_with_admin_cli(monkeypatch, tmp_path, capsys):
    _patch_settings(monkeypatch, tmp_path)
    main(["bootstrap-admin", "--email", "admin@b.c"])
    capsys.readouterr()
    rc = main(["create-invite", "--created-by", "admin@b.c", "--email-hint", "new@b.c"])
    assert rc == 0
    assert "/register?token=" in capsys.readouterr().out


def test_revoke_sessions_cli(monkeypatch, tmp_path, capsys):
    _patch_settings(monkeypatch, tmp_path)
    main(["bootstrap-admin", "--email", "admin@b.c"])
    capsys.readouterr()
    rc = main(["revoke-sessions", "--email", "admin@b.c"])
    assert rc == 0
    assert "Revoked" in capsys.readouterr().out


def test_revoke_sessions_unknown_user(monkeypatch, tmp_path):
    _patch_settings(monkeypatch, tmp_path)
    assert main(["revoke-sessions", "--email", "ghost@b.c"]) == 1


def test_send_flag_tolerates_email_failure(monkeypatch, tmp_path, capsys):
    # RESEND_API_KEY is empty → send raises EmailUnavailableError → CLI must not crash
    _patch_settings(monkeypatch, tmp_path)
    rc = main(["bootstrap-admin", "--email", "admin@b.c", "--send"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "email send failed" in out
