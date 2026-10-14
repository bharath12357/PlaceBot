import ai_service
import database

from conftest import new_conversation, register


# ------------------------------------------------------------------ auth
def test_register_login_logout_flow(client):
    res = register(client)
    assert res.status_code == 302 and res.headers["Location"].endswith("/")

    assert client.get("/").status_code == 200  # logged in after sign-up

    client.post("/logout")
    res = client.get("/")
    assert res.status_code == 302 and "/login" in res.headers["Location"]

    bad = client.post("/login", data={"username": "alice", "password": "wrong"})
    assert bad.status_code == 200 and b"Invalid username or password" in bad.data

    good = client.post("/login", data={"username": "alice", "password": "secret123"})
    assert good.status_code == 302


def test_duplicate_username_rejected_case_insensitive(client):
    register(client, "alice")
    client.post("/logout")
    res = register(client, "ALICE")
    assert res.status_code == 200 and b"already taken" in res.data


def test_register_validation(client):
    assert b"Username must be" in register(client, "a b", "secret123").data
    assert b"at least 6" in register(client, "bob", "123").data


def test_password_is_hashed(app, client):
    register(client, "alice", "secret123")
    with app.app_context():
        row = database.get_db().execute("SELECT password_hash FROM users").fetchone()
    assert row["password_hash"] != "secret123"
    assert "secret123" not in row["password_hash"]


def test_api_requires_login(client):
    assert client.get("/api/conversations").status_code == 401
    assert client.post("/api/conversations", json={}).status_code == 401


# ------------------------------------------------------------------ chat
def test_chat_is_saved_and_titled(client, fake_ai):
    register(client)
    conv_id = new_conversation(client, "dbms")

    res = client.post(f"/api/conversations/{conv_id}/chat", json={"message": "What is ACID?"})
    assert res.status_code == 200
    body = res.get_json()
    assert body["reply"] == "echo: What is ACID?"
    assert body["title"] == "What is ACID?"
    assert fake_ai[0]["topic"] == "dbms"

    msgs = client.get(f"/api/conversations/{conv_id}/messages").get_json()
    assert msgs == [
        {"role": "user", "content": "What is ACID?"},
        {"role": "model", "content": "echo: What is ACID?"},
    ]
    listing = client.get("/api/conversations").get_json()
    assert listing[0]["title"] == "What is ACID?"


def test_history_is_sent_to_ai(client, fake_ai):
    register(client)
    conv_id = new_conversation(client)
    client.post(f"/api/conversations/{conv_id}/chat", json={"message": "one"})
    client.post(f"/api/conversations/{conv_id}/chat", json={"message": "two"})
    second_call_history = fake_ai[1]["history"]
    assert [m["content"] for m in second_call_history] == ["one", "echo: one", "two"]


def test_history_survives_server_restart(tmp_path, fake_ai):
    from app import create_app

    config = {"TESTING": True, "DATABASE": str(tmp_path / "persist.db"), "SECRET_KEY": "k"}
    first = create_app(config).test_client()
    register(first)
    conv_id = new_conversation(first)
    first.post(f"/api/conversations/{conv_id}/chat", json={"message": "remember me"})

    second = create_app(config).test_client()  # "restarted" server, same database file
    second.post("/login", data={"username": "alice", "password": "secret123"})
    msgs = second.get(f"/api/conversations/{conv_id}/messages").get_json()
    assert len(msgs) == 2


def test_users_cannot_access_each_others_chats(app, fake_ai):
    alice = app.test_client()
    bob = app.test_client()
    register(alice, "alice")
    register(bob, "bob")
    conv_id = new_conversation(alice)
    alice.post(f"/api/conversations/{conv_id}/chat", json={"message": "secret"})

    assert bob.get(f"/api/conversations/{conv_id}/messages").status_code == 404
    assert bob.post(f"/api/conversations/{conv_id}/chat", json={"message": "hi"}).status_code == 404
    assert bob.delete(f"/api/conversations/{conv_id}").status_code == 404
    assert bob.get("/api/conversations").get_json() == []


def test_ai_failure_saves_nothing(client, monkeypatch):
    def boom(topic, history):
        raise RuntimeError("quota exceeded")

    monkeypatch.setattr("ai_service.generate_reply", boom)
    register(client)
    conv_id = new_conversation(client)

    res = client.post(f"/api/conversations/{conv_id}/chat", json={"message": "hello"})
    assert res.status_code == 502 and "quota exceeded" in res.get_json()["error"]
    assert client.get(f"/api/conversations/{conv_id}/messages").get_json() == []
    assert client.get("/api/conversations").get_json()[0]["title"] == "New chat"


def test_delete_conversation_removes_messages(app, client, fake_ai):
    register(client)
    conv_id = new_conversation(client)
    client.post(f"/api/conversations/{conv_id}/chat", json={"message": "hi"})

    assert client.delete(f"/api/conversations/{conv_id}").status_code == 200
    with app.app_context():
        count = database.get_db().execute("SELECT COUNT(*) AS n FROM messages").fetchone()["n"]
    assert count == 0  # ON DELETE CASCADE worked


def test_input_validation(client, fake_ai):
    register(client)
    conv_id = new_conversation(client, "not-a-real-topic")
    url = f"/api/conversations/{conv_id}/chat"

    assert client.post(url, json={"message": "   "}).status_code == 400
    assert client.post(url, json={"message": 123}).status_code == 400
    assert client.post(url, json={"message": "x" * 2001}).status_code == 400
    assert client.post(url, data="not json").status_code == 400
    assert client.get("/api/conversations").get_json()[0]["topic"] == "general"  # fell back


# -------------------------------------------------------------- ai_service
def test_trim_history_limits_and_starts_with_user():
    history = [{"role": "user" if i % 2 == 0 else "model", "content": str(i)} for i in range(30)]
    trimmed = ai_service.trim_history(history, limit=5)
    # the last 5 are 25..29, but 25 is a "model" message, so it is dropped
    assert [m["content"] for m in trimmed] == ["26", "27", "28", "29"]
    assert trimmed[0]["role"] == "user"


def test_prompt_includes_topic():
    assert "DBMS" in ai_service.build_prompt("dbms")
    assert "General Interview" in ai_service.build_prompt("unknown-topic")
