from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.core.config import Settings
from app.core.security import csrf_token, current_session, require_csrf, token_hash


def request_with_cookie(token: str) -> Request:
    return Request({"type": "http", "headers": [(b"cookie", f"speechflow_session={token}".encode())]})


def test_session_tokens_are_peppered_and_csrf_is_distinct() -> None:
    settings = Settings(session_token_pepper="test-pepper")
    assert token_hash("visitor-token", settings) != "visitor-token"
    assert csrf_token("visitor-token", settings) != token_hash("visitor-token", settings)


def test_expired_or_unknown_session_is_rejected() -> None:
    settings = Settings(session_token_pepper="test-pepper")
    expired = SimpleNamespace(expires_at=datetime.now(UTC) - timedelta(seconds=1))
    database = SimpleNamespace(scalar=lambda _query: expired)
    with pytest.raises(HTTPException, match="expired"):
        current_session(request_with_cookie("expired"), database, settings)
    database = SimpleNamespace(scalar=lambda _query: None)
    with pytest.raises(HTTPException, match="expired"):
        current_session(request_with_cookie("unknown"), database, settings)


def test_production_rejects_development_pepper_and_wildcard_cors() -> None:
    with pytest.raises(ValueError):
        Settings(environment="production")
    with pytest.raises(ValueError):
        Settings(allowed_origins=["*"])


def test_csrf_requires_matching_token_and_allowed_origin() -> None:
    settings = Settings(session_token_pepper="test-pepper", allowed_origins=["http://localhost:3000"])
    token = "visitor-token"
    session = SimpleNamespace(id="session-a")
    request = Request({"type": "http", "headers": [(b"origin", b"http://localhost:3000"), (b"cookie", f"speechflow_session={token}".encode()), (b"x-csrf-token", csrf_token(token, settings).encode())]})
    assert require_csrf(request, session, settings) is session
    invalid_origin = Request({"type": "http", "headers": [(b"origin", b"https://attacker.example"), (b"cookie", f"speechflow_session={token}".encode()), (b"x-csrf-token", csrf_token(token, settings).encode())]})
    with pytest.raises(HTTPException, match="CSRF"):
        require_csrf(invalid_origin, session, settings)
