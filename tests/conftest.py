import pytest

from app import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(
        {"TESTING": True, "DATABASE": str(tmp_path / "test.db"), "SECRET_KEY": "test-key"}
    )


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def fake_ai(monkeypatch):
    """Replace the Gemini call so tests never need an API key or internet."""
    calls = []

    def fake_generate_reply(topic, history):
        calls.append({"topic": topic, "history": list(history)})
        return "echo: " + history[-1]["content"]

    monkeypatch.setattr("ai_service.generate_reply", fake_generate_reply)
    return calls


def register(client, username="alice", password="secret123"):
    return client.post("/register", data={"username": username, "password": password})


def new_conversation(client, topic="general"):
    res = client.post("/api/conversations", json={"topic": topic})
    assert res.status_code == 201
    return res.get_json()["id"]
