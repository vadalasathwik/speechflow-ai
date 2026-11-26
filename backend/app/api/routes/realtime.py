from __future__ import annotations

import asyncio
import json
import uuid

import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.config import get_settings
from app.services.realtime import Mode, RealtimeError, append_without_overlap, get_realtime_transcriber, pcm16_to_mono_16k

router = APIRouter()
MODES = {"auto", "en", "hi", "hi-en"}


@router.websocket("/ws/transcribe")
async def transcribe_live(websocket: WebSocket) -> None:
    settings = get_settings()
    origin = websocket.headers.get("origin")
    allowed = {str(item).rstrip("/") for item in settings.allowed_origins}
    if origin and origin.rstrip("/") not in allowed:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    session_id, mode, sample_rate, channels = str(uuid.uuid4()), "auto", 0, 0
    buffer = np.empty(0, dtype=np.float32)
    session_audio = np.empty(0, dtype=np.float32)
    finalized = ""
    sequence = 0
    total_bytes = 0
    started = asyncio.get_running_loop().time()
    active = False
    detected_language: str | None = None
    language_probability: float | None = None
    async def emit(kind: str, **payload: object) -> None:
        nonlocal sequence
        sequence += 1
        await websocket.send_json({"type": kind, "session_id": session_id, "sequence": sequence, **payload})
    async def flush(final: bool = False) -> None:
        nonlocal buffer, finalized, detected_language, language_probability
        samples = session_audio if final else buffer
        if not len(samples):
            return
        result = await asyncio.to_thread(get_realtime_transcriber().infer, samples, mode, final)  # blocking inference stays off-loop
        if result.detected_language is not None:
            detected_language = result.detected_language
            language_probability = result.language_probability
        if result.text:
            candidate = append_without_overlap(finalized, result.text)
            if final:
                # A successful final pass uses every accepted PCM sample, not only the tail window.
                finalized = result.text
                await emit("final", text=finalized, audio_end_seconds=total_bytes / (sample_rate * channels * 2), processing_seconds=result.processing_seconds, detected_language=detected_language, language_probability=language_probability)
            else:
                await emit("partial", text=candidate, audio_end_seconds=total_bytes / (sample_rate * channels * 2), processing_seconds=result.processing_seconds, detected_language=detected_language, language_probability=language_probability)
        if final:
            buffer = np.empty(0, dtype=np.float32)
        else:
            keep = int(settings.realtime_overlap_seconds * 16000)
            buffer = buffer[-keep:] if keep else np.empty(0, dtype=np.float32)
    try:
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                return
            if message.get("text"):
                try:
                    event = json.loads(message["text"])
                except json.JSONDecodeError:
                    await emit("error", code="invalid_message", message="Messages must be JSON."); continue
                action = event.get("type")
                if action == "start" and not active:
                    mode = event.get("recognition_mode", "auto")
                    sample_rate, channels = int(event.get("sample_rate", 0)), int(event.get("channels", 0))
                    if mode not in MODES or sample_rate < 8000 or channels not in {1, 2} or event.get("pcm_format") != "s16le":
                        await emit("error", code="invalid_start", message="Use a supported mode and s16le PCM."); continue
                    active = True
                    await emit("ready", sample_rate=sample_rate, channels=channels, pcm_format="s16le")
                elif action == "stop" and active:
                    await flush(True); await emit("completed", text=finalized, detected_language=detected_language, language_probability=language_probability); return
                elif action == "cancel":
                    await emit("completed", text=finalized, cancelled=True); return
                else:
                    await emit("error", code="invalid_state", message="Send start before audio, then stop or cancel.")
            elif message.get("bytes") is not None:
                if not active:
                    await emit("error", code="invalid_state", message="Send start before audio."); continue
                data = message["bytes"]
                total_bytes += len(data)
                if total_bytes > settings.max_realtime_audio_bytes or asyncio.get_running_loop().time() - started > settings.max_realtime_session_seconds:
                    await emit("error", code="limit_exceeded", message="Live session limit reached."); return
                decoded = pcm16_to_mono_16k(data, sample_rate, channels)
                buffer = np.concatenate((buffer, decoded))
                session_audio = np.concatenate((session_audio, decoded))
                if len(buffer) >= int(settings.realtime_window_seconds * 16000):
                    await flush()
    except (RealtimeError, ValueError) as exc:
        await emit("error", code="audio_or_inference_error", message=str(exc))
    except WebSocketDisconnect:
        return
