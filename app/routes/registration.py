"""Customer onboarding: the sign-up form and the thank-you page."""

from flask import Blueprint, redirect, render_template, request, session, url_for

from app import services
from app.routes import form_without_password
from app.validation import client_config, validate_registration

bp = Blueprint("registration", __name__)


@bp.get("/")
def index():
    return redirect(url_for("registration.register"))


@bp.get("/register")
def register():
    return _render_register(form={}, errors={})


@bp.post("/register")
def register_submit():
    registration, errors = validate_registration(request.form, services.get_dial_codes())
    if errors:
        return _render_register(request.form, errors), 400

    try:
        services.register_customer(registration)
    except services.EmailAlreadyRegistered:
        errors = {"email": "This email is already registered. Please log in instead."}
        return _render_register(request.form, errors), 409

    # Post/Redirect/Get: refreshing the thank-you page must not resubmit the form.
    session["registered_name"] = registration.first_name
    return redirect(url_for("registration.register_success"))


@bp.get("/register/success")
def register_success():
    # One-time page: the name is removed from the session as it is shown.
    first_name = session.pop("registered_name", None)
    if first_name is None:
        return redirect(url_for("registration.register"))
    return render_template("register_success.html", first_name=first_name)


def _render_register(form, errors):
    return render_template(
        "register.html",
        countries=services.get_countries(),
        form=form_without_password(form),
        errors=errors,
        validation_config=client_config(),
    )
