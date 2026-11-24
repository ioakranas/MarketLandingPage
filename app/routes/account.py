"""Pages for logged-in customers."""

from flask import Blueprint, g, render_template

from app import services
from app.routes.auth import login_required

bp = Blueprint("account", __name__)


@bp.get("/welcome")
@login_required
def welcome():
    return render_template(
        "welcome.html", customer=g.customer, stats=services.get_login_stats(g.customer["id"])
    )
