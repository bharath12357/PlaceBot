"""SQLite helpers: one connection per request, schema created on startup."""
import sqlite3

from flask import current_app, g


def get_db():
    """Return this request's database connection (created on first use)."""
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row  # access columns by name
        g.db.execute("PRAGMA foreign_keys = ON")  # needed for ON DELETE CASCADE
    return g.db


def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Create tables from schema.sql if they don't already exist."""
    db = get_db()
    with current_app.open_resource("schema.sql") as f:
        db.executescript(f.read().decode("utf-8"))
    db.commit()


def init_app(app):
    app.teardown_appcontext(close_db)
    with app.app_context():
        init_db()
