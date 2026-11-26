import os
import logging
import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool

from app.core.config import Settings, get_settings
from app.schemas.transcription import TranscriptionResponse, TranscriptionSegment
from app.services.transcription import (
    FasterWhisperTranscriptionService,
    InferenceError,
    InvalidAudioError,
    ModelInitializationError,
    get_audio_duration,
    get_transcription_service,
)

router = APIRouter(tags=["transcription"])
logger = logging.getLogger(__name__)
SUPPORTED_SUFFIXES = {".wav", ".mp3", ".m4a", ".mp4", ".webm"}
CHUNK_SIZE = 1024 * 1024


async def persist_upload(upload: UploadFile, maximum_bytes: int) -> Path:
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Unsupported audio format.")
    temp_file = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    path = Path(temp_file.name)
    total_bytes = 0
    try:
        with temp_file:
            while chunk := await upload.read(CHUNK_SIZE):
                total_bytes += len(chunk)
                if total_bytes > maximum_bytes:
                    raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="Audio file exceeds the configured size limit.")
                temp_file.write(chunk)
        if total_bytes == 0:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Audio file is empty.")
        logger.info("Received audio upload: filename=%s mime_type=%s size_bytes=%d", upload.filename, upload.content_type, total_bytes)
        return path
    except Exception:
        path.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()


@router.post("/transcribe", response_model=TranscriptionResponse, status_code=status.HTTP_200_OK)
async def transcribe_audio(
    file: Annotated[UploadFile, File(description="WAV, MP3, M4A, or WebM audio")],
    language: Annotated[str | None, Form()] = None,
    settings: Settings = Depends(get_settings),
    service: FasterWhisperTranscriptionService = Depends(get_transcription_service),
) -> TranscriptionResponse:
    selected_language = language or settings.whisper_language
    if selected_language not in {"auto", "en", "hi", "hi-en"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Language must be auto, en, hi, or hi-en.")

    path = await persist_upload(file, settings.max_audio_size_mb * 1024 * 1024)
    try:
        duration = await run_in_threadpool(get_audio_duration, path)
        if duration > settings.max_audio_duration_seconds:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Audio exceeds the configured duration limit.")
        result = await run_in_threadpool(service.transcribe, path, selected_language)
        return TranscriptionResponse(
            text=result.text,
            language=result.language,
            language_probability=result.language_probability,
            duration_seconds=result.duration_seconds,
            processing_time_seconds=result.processing_time_seconds,
            real_time_factor=round(result.processing_time_seconds / result.duration_seconds, 3) if result.duration_seconds else 0,
            model=result.model,
            recognition_mode=result.recognition_mode,
            conditioned_language=result.conditioned_language,
            output_script=result.output_script,
            script_warning=result.script_warning,
            original_text=result.original_text,
            quality_warning=result.quality_warning,
            retry_performed=result.retry_performed,
            segments=[TranscriptionSegment(start=item.start, end=item.end, text=item.text) for item in result.segments],
        )
    except InvalidAudioError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="The uploaded file is not valid audio.") from None
    except ModelInitializationError:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Speech recognition model is unavailable.") from None
    except InferenceError:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Speech recognition failed.") from None
    finally:
        path.unlink(missing_ok=True)
