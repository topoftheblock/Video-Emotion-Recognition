"""
Tests that create_app() wires up the HTTP surface the frontend expects.

These are possible at all because create_app() is a factory: building
an app is an explicit call, so a test can point the video store at a
tmp dir first. Only the paths that need neither Postgres nor a
configured LLM are asserted here -- the rest is covered by the
DB-backed tests, which skip without a database.
"""

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    # create_app() creates the video store and mounts it as static
    # files. Redirected to a tmp dir so running the suite never leaves
    # a stray `cas/` directory next to wherever pytest was invoked.
    monkeypatch.setattr("backend.app.VIDEO_DIR", tmp_path / "videos")
    return TestClient(create_app())


def test_every_api_route_is_registered(client):
    # Asserted through the OpenAPI schema rather than app.routes:
    # FastAPI keeps an included router as a single wrapper entry in
    # app.routes instead of flattening its endpoints into it, so the
    # concrete paths are only visible here.
    paths = client.get("/openapi.json").json()["paths"]
    assert {
        "/healthz",
        "/api/videos",
        "/api/videos/{video_id}/data",
        "/api/persons/global",
        "/api/stats/{video_id}",
        "/api/ask",
        "/api/jobs",
    } <= set(paths)
    assert "post" in paths["/api/ask"]
    assert "get" in paths["/api/videos"]


def test_ask_rejects_a_blank_question_before_calling_the_agent(client):
    # Whitespace only: must 400 on our side rather than spend an LLM
    # round-trip discovering there is no question.
    response = client.post("/api/ask", json={"question": "   "})
    assert response.status_code == 400
    assert response.json()["detail"] == "question must not be empty"


def test_ask_requires_a_question_field(client):
    assert client.post("/api/ask", json={}).status_code == 422


def test_frontend_is_served_at_the_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_video_store_is_mounted_under_media(client):
    # Nothing in the tmp store, so a 404 from the mount (not a 405 or a
    # fall-through to the frontend's index.html) is what proves /media
    # is a StaticFiles mount rather than an unhandled path.
    assert client.get("/media/does-not-exist.mp4").status_code == 404
