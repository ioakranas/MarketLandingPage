"""Maintenance commands, run with ``flask --app app <command>``."""

import click
from flask import Flask
from flask.cli import with_appcontext

from app import services


@click.command("purge-login-attempts")
@click.option("--days", default=30, show_default=True, type=click.IntRange(min=1),
              help="Delete failed attempts older than this many days.")
@with_appcontext
def purge_login_attempts_command(days: int) -> None:
    """Retention for login_attempts (in production: a scheduled job)."""
    deleted = services.purge_failed_login_attempts(days)
    click.echo(f"Deleted {deleted} failed login attempt(s) older than {days} day(s).")


def init_app(app: Flask) -> None:
    app.cli.add_command(purge_login_attempts_command)
