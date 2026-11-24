"""Application factory.

Flask apps are usually built by a ``create_app`` function instead of a module-level
global. That lets tests create isolated app instances with their own configuration
(e.g. a temporary database), much like a Spring test context.
"""

import os
import secrets

from flask import Flask, render_template
from flask_wtf.csrf import CSRFError, CSRFProtect

csrf = CSRFProtect()


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)

    app.config.from_mapping(
        # In production SECRET_KEY must come from the environment. Without it we fall
        # back to a random per-process key: safe, but sessions reset on every restart.
        SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
        # The SQLite file lives in Flask's instance/ folder, which is git-ignored.
        DATABASE=os.path.join(app.instance_path, "hfmarkets.sqlite3"),
        # Session cookie hardening: no JS access, not sent on cross-site POSTs.
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        # Enable when served over HTTPS (always, in production).
        SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE") == "1",
    )

    app.config.update(test_config or {})

    os.makedirs(app.instance_path, exist_ok=True)

    from app import auth, db

    db.init_app(app)
    # Every POST must carry a valid token from a page we rendered (blocks cross-site
    # form submissions made from another origin in the user's browser).
    csrf.init_app(app)
    app.register_blueprint(auth.bp)

    @app.errorhandler(CSRFError)
    def handle_csrf_error(_error):
        message = "Your session has expired. Please reload the page and try again."
        return render_template("error.html", message=message), 400

    return app
