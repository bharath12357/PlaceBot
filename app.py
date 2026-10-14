"""PlaceBot: AI placement interview coach (Flask + SQLite + Google Gemini)."""
import os
import re
import secrets
import sqlite3
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

import ai_service
import database

load_dotenv()

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,30}$")
MIN_PASSWORD_LEN = 6
MAX_MESSAGE_LEN = 2000
DEFAULT_TITLE = "New chat"


def login_required(view):
    """Redirect page requests to /login; return 401 JSON for API requests."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            if request.path.startswith("/api/"):
                return jsonify({"error": "Please log in."}), 401
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


def json_body():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def make_title(message):
    message = " ".join(message.split())
    return message if len(message) <= 40 else message[:40].rstrip() + "..."


def get_owned_conversation(conv_id):
    """Fetch a conversation only if it belongs to the logged-in user."""
    return database.get_db().execute(
        "SELECT id, title, topic FROM conversations WHERE id = ? AND user_id = ?",
        (conv_id, g.user["id"]),
    ).fetchone()


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.getenv("SECRET_KEY") or secrets.token_hex(32),
        DATABASE=os.path.join(app.root_path, "placebot.db"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    if test_config:
        app.config.update(test_config)

    database.init_app(app)

    @app.before_request
    def load_logged_in_user():
        g.user = None
        if request.endpoint == "static":
            return
        user_id = session.get("user_id")
        if user_id is not None:
            g.user = database.get_db().execute(
                "SELECT id, username FROM users WHERE id = ?", (user_id,)
            ).fetchone()

    # ------------------------------------------------------------------ pages
    @app.route("/")
    @login_required
    def index():
        topic_labels = {key: t["label"] for key, t in ai_service.TOPICS.items()}
        return render_template("chat.html", topic_labels=topic_labels)

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if g.user:
            return redirect(url_for("index"))
        error = None
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            if not USERNAME_RE.match(username):
                error = "Username must be 3-30 characters: letters, numbers or underscore."
            elif len(password) < MIN_PASSWORD_LEN:
                error = f"Password must be at least {MIN_PASSWORD_LEN} characters."
            else:
                db = database.get_db()
                try:
                    cur = db.execute(
                        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                        (username, generate_password_hash(password)),
                    )
                    db.commit()
                except sqlite3.IntegrityError:
                    error = "That username is already taken."
                else:
                    session.clear()
                    session["user_id"] = cur.lastrowid
                    return redirect(url_for("index"))
        return render_template("register.html", error=error)

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if g.user:
            return redirect(url_for("index"))
        error = None
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            user = database.get_db().execute(
                "SELECT id, password_hash FROM users WHERE username = ?", (username,)
            ).fetchone()
            if user is None or not check_password_hash(user["password_hash"], password):
                error = "Invalid username or password."
            else:
                session.clear()
                session["user_id"] = user["id"]
                return redirect(url_for("index"))
        return render_template("login.html", error=error)

    @app.route("/logout", methods=["POST"])
    def logout():
        session.clear()
        return redirect(url_for("login"))

    # -------------------------------------------------------------------- API
    @app.route("/api/conversations", methods=["GET"])
    @login_required
    def list_conversations():
        rows = database.get_db().execute(
            "SELECT id, title, topic FROM conversations WHERE user_id = ? ORDER BY id DESC",
            (g.user["id"],),
        ).fetchall()
        return jsonify([dict(r) for r in rows])

    @app.route("/api/conversations", methods=["POST"])
    @login_required
    def create_conversation():
        topic = json_body().get("topic")
        if topic not in ai_service.TOPICS:
            topic = "general"
        db = database.get_db()
        cur = db.execute(
            "INSERT INTO conversations (user_id, title, topic) VALUES (?, ?, ?)",
            (g.user["id"], DEFAULT_TITLE, topic),
        )
        db.commit()
        return jsonify({"id": cur.lastrowid, "title": DEFAULT_TITLE, "topic": topic}), 201

    @app.route("/api/conversations/<int:conv_id>/messages", methods=["GET"])
    @login_required
    def get_messages(conv_id):
        if get_owned_conversation(conv_id) is None:
            return jsonify({"error": "Conversation not found."}), 404
        rows = database.get_db().execute(
            "SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY id",
            (conv_id,),
        ).fetchall()
        return jsonify([dict(r) for r in rows])

    @app.route("/api/conversations/<int:conv_id>", methods=["DELETE"])
    @login_required
    def delete_conversation(conv_id):
        if get_owned_conversation(conv_id) is None:
            return jsonify({"error": "Conversation not found."}), 404
        db = database.get_db()
        db.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
        db.commit()
        return jsonify({"status": "deleted"})

    @app.route("/api/conversations/<int:conv_id>/chat", methods=["POST"])
    @login_required
    def chat(conv_id):
        conv = get_owned_conversation(conv_id)
        if conv is None:
            return jsonify({"error": "Conversation not found."}), 404

        message = json_body().get("message")
        if not isinstance(message, str) or not message.strip():
            return jsonify({"error": "Message cannot be empty."}), 400
        message = message.strip()
        if len(message) > MAX_MESSAGE_LEN:
            return jsonify({"error": f"Message is too long (max {MAX_MESSAGE_LEN} characters)."}), 400

        db = database.get_db()
        rows = db.execute(
            "SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY id",
            (conv_id,),
        ).fetchall()
        history = [{"role": r["role"], "content": r["content"]} for r in rows]
        history.append({"role": "user", "content": message})

        # Call the AI first. Only save the exchange if it succeeds, so a failed
        # request never leaves a half-finished conversation in the database.
        try:
            reply = ai_service.generate_reply(conv["topic"], history)
        except Exception as exc:
            app.logger.exception("AI request failed")
            return jsonify({"error": f"AI error: {str(exc)[:300]}"}), 502

        db.execute(
            "INSERT INTO messages (conversation_id, role, content) VALUES (?, 'user', ?)",
            (conv_id, message),
        )
        db.execute(
            "INSERT INTO messages (conversation_id, role, content) VALUES (?, 'model', ?)",
            (conv_id, reply),
        )
        title = conv["title"]
        if title == DEFAULT_TITLE:
            title = make_title(message)
            db.execute("UPDATE conversations SET title = ? WHERE id = ?", (title, conv_id))
        db.commit()
        return jsonify({"reply": reply, "title": title})

    return app


if __name__ == "__main__":
    # For deployment use:  gunicorn "app:create_app()"
    create_app().run(debug=True, port=int(os.getenv("PORT", 5000)))
