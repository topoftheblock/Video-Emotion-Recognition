"""Tests that `create_app` wires up the surface the frontend expects.

These are possible at all because it is a factory: building an app is
an explicit call, so a test can point the video store somewhere
temporary first. Only the paths needing neither a database nor a
configured model are asserted here.
"""

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app


@pytest.fixture
def client(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """An app whose video store points somewhere temporary.

    `create_app` creates that directory and mounts it, so redirecting
    it keeps the suite from leaving a stray directory wherever pytest
    was invoked.
    """
    monkeypatch.setattr("backend.app.VIDEO_DIR", tmp_path / "videos")
    return TestClient(create_app())


def test_every_api_route_is_registered(client: TestClient) -> None:
    """Every endpoint the frontend calls is actually mounted.

    Asserted through the OpenAPI schema rather than the route table: an
    included router appears there as a single wrapper entry rather than
    as its own endpoints, so the concrete paths are only visible here.
    """
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


def test_ask_rejects_a_blank_question_before_calling_the_agent(
    client: TestClient,
) -> None:
    """A blank question is refused here, not by the model.

    Whitespace only: answering it costs a round-trip to discover there
    was no question.
    """
    response = client.post("/api/ask", json={"question": "   "})
    assert response.status_code == 400
    assert response.json()["detail"] == "question must not be empty"


def test_ask_requires_a_question_field(client: TestClient) -> None:
    """A request with no question at all fails validation."""
    assert client.post("/api/ask", json={}).status_code == 422


def test_frontend_is_served_at_the_root(client: TestClient) -> None:
    """The static frontend is what "/" serves."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_video_store_is_mounted_under_media(client: TestClient) -> None:
    """The video store is mounted, and not shadowed by the catch-all.

    The store is empty here, so a 404 from the mount — rather than a
    405, or a fall-through serving the frontend's page — is what shows
    it is a real static mount.
    """
    assert client.get("/media/does-not-exist.mp4").status_code == 404
