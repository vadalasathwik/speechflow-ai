import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.anonymous_session import AnonymousSession


def token_hash(token: str, settings: Settings) -> str:
    return hmac.new(settings.session_token_pepper.encode(), token.encode(), hashlib.sha256).hexdigest()


def csrf_token(token: str, settings: Settings) -> str:
    return hmac.new(settings.session_token_pepper.encode(), f"csrf:{token}".encode(), hashlib.sha256).hexdigest()


def new_session(db: Session, settings: Settings) -> tuple[AnonymousSession, str]:
    token = secrets.token_urlsafe(32)
    session = AnonymousSession(token_hash=token_hash(token, settings), expires_at=datetime.now(UTC) + timedelta(days=settings.session_duration_days))
    db.add(session)
    db.commit()
    db.refresh(session)
    return session, token


def current_session(request: Request, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)) -> AnonymousSession:
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Anonymous session is required.")
    session = db.scalar(select(AnonymousSession).where(AnonymousSession.token_hash == token_hash(token, settings)))
    if session is None or session.expires_at <= datetime.now(UTC):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Anonymous session expired. Start a new session.")
    return session


def require_csrf(request: Request, session: AnonymousSession = Depends(current_session), settings: Settings = Depends(get_settings)) -> AnonymousSession:
    origin = request.headers.get("origin")
    allowed = {str(value).rstrip("/") for value in settings.allowed_origins}
    token = request.cookies.get(settings.session_cookie_name)
    supplied = request.headers.get("x-csrf-token")
    if not origin or origin.rstrip("/") not in allowed or not token or not supplied or not hmac.compare_digest(supplied, csrf_token(token, settings)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed.")
    return session
