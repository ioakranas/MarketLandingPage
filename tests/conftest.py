"""Shared pytest fixtures (pytest discovers this file automatically)."""

import pytest

from app import create_app


@pytest.fixture
def app(tmp_path):
    """A fresh app per test, backed by a throwaway database file."""
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "DATABASE": str(tmp_path / "test.sqlite3"),
        }
    )
    yield app


@pytest.fixture
def client(app):
    """HTTP test client, similar to Spring's MockMvc."""
    return app.test_client()
