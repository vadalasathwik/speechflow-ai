import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.transcription import SavedTranscription
from app.schemas.saved_transcription import TranscriptionCreate, TranscriptionPage, TranscriptionRead, TranscriptionUpdate

router = APIRouter(tags=["transcriptions"])
Db = Annotated[Session, Depends(get_db)]


def missing() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transcription not found.")


@router.post("/transcriptions", response_model=TranscriptionRead, status_code=status.HTTP_201_CREATED)
def create_transcription(payload: TranscriptionCreate, db: Db) -> SavedTranscription:
    item = SavedTranscription(**payload.model_dump())
    try:
        db.add(item)
        db.commit()
        db.refresh(item)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Unable to save transcription.") from None
    return item


@router.get("/transcriptions", response_model=TranscriptionPage)
def list_transcriptions(
    db: Db,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    search: Annotated[str | None, Query(max_length=255)] = None,
    language: Annotated[str | None, Query(max_length=16)] = None,
) -> TranscriptionPage:
    query = select(SavedTranscription)
    if search:
        pattern = f"%{search}%"
        query = query.where(
            or_(SavedTranscription.title.ilike(pattern), SavedTranscription.text.ilike(pattern))
        )
    if language:
        query = query.where(SavedTranscription.detected_language == language)
    try:
        total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
        items = list(
            db.scalars(
                query.order_by(SavedTranscription.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
    except SQLAlchemyError:
        raise HTTPException(status_code=500, detail="Unable to load transcriptions.") from None
    return TranscriptionPage(items=items, total=total, page=page, page_size=page_size)


@router.get("/transcriptions/{transcription_id}", response_model=TranscriptionRead)
def get_transcription(transcription_id: uuid.UUID, db: Db) -> SavedTranscription:
    item = db.get(SavedTranscription, transcription_id)
    if item is None:
        raise missing()
    return item


@router.patch("/transcriptions/{transcription_id}", response_model=TranscriptionRead)
def update_transcription(transcription_id: uuid.UUID, payload: TranscriptionUpdate, db: Db) -> SavedTranscription:
    item = db.get(SavedTranscription, transcription_id)
    if item is None:
        raise missing()
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    try:
        db.commit()
        db.refresh(item)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Unable to update transcription.") from None
    return item


@router.delete("/transcriptions/{transcription_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transcription(transcription_id: uuid.UUID, db: Db) -> None:
    item = db.get(SavedTranscription, transcription_id)
    if item is None:
        raise missing()
    try:
        db.delete(item)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Unable to delete transcription.") from None
