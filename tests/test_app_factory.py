from app import create_app


def test_test_config_overrides_defaults(app):
    assert app.testing is True
    assert app.config["SECRET_KEY"] == "test-secret"
    assert app.config["DATABASE"].endswith("test.sqlite3")


def test_secret_key_read_from_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("SECRET_KEY", "from-env")
    app = create_app({"DATABASE": str(tmp_path / "db.sqlite3")})
    assert app.config["SECRET_KEY"] == "from-env"


def test_random_secret_key_when_environment_missing(monkeypatch, tmp_path):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    database = {"DATABASE": str(tmp_path / "db.sqlite3")}
    first = create_app(database).config["SECRET_KEY"]
    second = create_app(database).config["SECRET_KEY"]
    assert len(first) == 64
    assert first != second


def test_session_cookie_is_hardened(app):
    assert app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
