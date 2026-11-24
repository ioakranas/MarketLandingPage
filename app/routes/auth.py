"""Authentication: login, logout and the guard for pages that require a logged-in customer."""

import functools

from flask import Blueprint, g, redirect, render_template, request, session, url_for

from app import services
from app.routes import form_without_password
from app.validation import validate_login

bp = Blueprint("auth", __name__)


def login_required(view):
    """Decorator for protected pages (comparable to a Spring Security filter).

    Loads the logged-in customer into ``g.customer``, or redirects to the login page.
    The customer is re-read on every request, so a deleted account loses access at once.
    """

    @functools.wraps(view)
    def wrapped_view(*args, **kwargs):
        customer_id = session.get("customer_id")
        customer = services.get_customer(customer_id) if customer_id else None
        if customer is None:
            session.clear()
            return redirect(url_for("auth.login"))
        g.customer = customer
        return view(*args, **kwargs)

    return wrapped_view


@bp.get("/login")
def login():
    return _render_login(form={}, errors={})


@bp.post("/login")
def login_submit():
    credentials, errors = validate_login(request.form)
    if errors:
        return _render_login(request.form, errors), 400

    try:
        customer = services.authenticate(credentials, request.remote_addr)
    except services.InvalidCredentials:
        # One message for unknown email and wrong password: no hint which one it was.
        return _render_login(request.form, {"form": "Invalid email or password."}), 401
    except services.AccountLocked as locked:
        message = (
            "Too many failed login attempts. "
            f"Please try again in {locked.minutes_remaining} minute(s)."
        )
        return _render_login(request.form, {"form": message}), 429

    # A fresh session on login prevents session fixation: any session data an attacker
    # may have planted before authentication is discarded.
    session.clear()
    session["customer_id"] = customer["id"]
    return redirect(url_for("account.welcome"))


@bp.post("/logout")
def logout():
    # POST (CSRF-protected) rather than GET, so another site can't log users out.
    session.clear()
    return redirect(url_for("auth.login"))


def _render_login(form, errors):
    return render_template("login.html", form=form_without_password(form), errors=errors)
