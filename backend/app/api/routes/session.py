from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import csrf_token, new_session, token_hash
from app.db.session import get_db
from app.models.anonymous_session import AnonymousSession

router = APIRouter(tags=["session"])


def set_cookies(response: Response, token: str, settings: Settings) -> None:
    secure = settings.environment == "production"
    max_age = settings.session_duration_days * 24 * 60 * 60
    response.set_cookie(settings.session_cookie_name, token, max_age=max_age, httponly=True, secure=secure, samesite=settings.session_cookie_samesite)
    response.set_cookie(settings.csrf_cookie_name, csrf_token(token, settings), max_age=max_age, httponly=False, secure=secure, samesite=settings.session_cookie_samesite)


@router.get("/session")
def bootstrap_session(request: Request, response: Response, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)) -> dict[str, str]:
    token = request.cookies.get(settings.session_cookie_name)
    session = db.scalar(select(AnonymousSession).where(AnonymousSession.token_hash == token_hash(token, settings))) if token else None
    if session is None or session.expires_at <= datetime.now(UTC):
        session, token = new_session(db, settings)
    assert token is not None
    set_cookies(response, token, settings)
    return {"expires_at": session.expires_at.isoformat(), "csrf_token": csrf_token(token, settings)}
