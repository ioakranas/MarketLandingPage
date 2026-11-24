"""SQLite connection handling and schema initialisation.

One connection per request: it is opened lazily on first use, stored on Flask's ``g``
object (request-scoped storage) and closed automatically when the request ends.
"""

import sqlite3

import click
from flask import Flask, current_app, g
from flask.cli import with_appcontext


def get_db() -> sqlite3.Connection:
    """Return the connection for the current request, opening it on first use."""
    if "db" not in g:
        connection = sqlite3.connect(current_app.config["DATABASE"])
        # Rows behave like dicts: row["email"] instead of row[5].
        connection.row_factory = sqlite3.Row
        # SQLite ignores foreign keys unless enabled, and the setting is per connection.
        connection.execute("PRAGMA foreign_keys = ON")
        g.db = connection
    return g.db


def close_db(_exception: BaseException | None = None) -> None:
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def init_db() -> None:
    """Create the tables and seed reference data. Safe to run any number of times."""
    schema = current_app.open_resource("schema.sql").read().decode("utf-8")
    db = get_db()
    db.executescript(schema)
    db.commit()


@click.command("init-db")
@with_appcontext
def init_db_command() -> None:
    """CLI entry point: ``flask --app app init-db``."""
    init_db()
    click.echo("Database initialised.")


def init_app(app: Flask) -> None:
    """Register DB hooks on the app and make sure the schema exists."""
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
    with app.app_context():
        init_db()
