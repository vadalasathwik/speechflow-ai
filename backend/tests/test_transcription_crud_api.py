from collections.abc import Generator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.core.security import current_session, require_csrf
from app.main import app
from app.models.anonymous_session import AnonymousSession
from app.models.transcription import SavedTranscription


class FakeSession:
    """Small unit-test double; PostgreSQL remains the only integration database."""

    def __init__(self) -> None:
        self.items: dict[UUID, SavedTranscription] = {}
        self.pending: list[SavedTranscription] = []

    def add(self, item: SavedTranscription) -> None:
        self.pending.append(item)

    def commit(self) -> None:
        now = datetime.now(UTC)
        for item in self.pending:
            item.id = item.id or uuid4()
            item.created_at = item.created_at or now
            item.updated_at = now
            self.items[item.id] = item
        self.pending.clear()

    def refresh(self, item: SavedTranscription) -> None:
        return None

    def get(self, _model: type[SavedTranscription], item_id: UUID) -> SavedTranscription | None:
        return self.items.get(item_id)

    def delete(self, item: SavedTranscription) -> None:
        self.items.pop(item.id, None)

    def scalar(self, _statement: object) -> int:
        descriptions = getattr(_statement, "column_descriptions", [])
        if descriptions and descriptions[0].get("entity") is SavedTranscription:
            return next(iter(self.items.values()), None)  # type: ignore[return-value]
        return len(self.items)

    def scalars(self, _statement: object) -> list[SavedTranscription]:
        return sorted(self.items.values(), key=lambda item: item.created_at, reverse=True)

    def rollback(self) -> None:
        return None


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    database = FakeSession()
    session = AnonymousSession(id=uuid4(), token_hash="test", expires_at=datetime.now(UTC))

    def override_get_db() -> Generator[FakeSession, None, None]:
        yield database

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[current_session] = lambda: session
    app.dependency_overrides[require_csrf] = lambda: session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_create_and_retrieve_unicode_transcription(client: TestClient) -> None:
    created = client.post(
        "/api/transcriptions",
        json={
            "title": "Mixed note",
            "text": "नमस्ते, आज हमारी meeting है",
            "source_type": "recording",
            "detected_language": "hi",
        },
    )

    assert created.status_code == 201
    assert created.json()["text"] == "नमस्ते, आज हमारी meeting है"

    fetched = client.get(f"/api/transcriptions/{created.json()['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["title"] == "Mixed note"


def test_list_update_delete_and_unknown_record(client: TestClient) -> None:
    created = client.post(
        "/api/transcriptions",
        json={"title": "English", "text": "Hello", "source_type": "upload"},
    )
    transcription_id = created.json()["id"]

    listed = client.get("/api/transcriptions?page=1&page_size=20&search=Hello")
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    updated = client.patch(
        f"/api/transcriptions/{transcription_id}",
        json={"title": "Updated", "text": "Hello everyone"},
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Updated"

    assert client.delete(f"/api/transcriptions/{transcription_id}").status_code == 204
    assert client.get(f"/api/transcriptions/{transcription_id}").status_code == 404
    assert client.get(f"/api/transcriptions/{uuid4()}").status_code == 404


def test_crud_validation_and_page_bounds(client: TestClient) -> None:
    assert client.post("/api/transcriptions", json={"title": " ", "text": "text", "source_type": "upload"}).status_code == 422
    assert client.get("/api/transcriptions?page_size=101").status_code == 422
    assert client.patch(f"/api/transcriptions/{uuid4()}", json={}).status_code == 422
