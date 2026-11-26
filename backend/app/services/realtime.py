"""Bounded, buffered Faster-Whisper inference for PCM WebSocket sessions."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Literal

import numpy as np

from app.core.config import Settings, get_settings
from app.services.script_detection import detect_output_script, has_hindi_candidate_evidence
from app.services.transcription_quality import assess_transcription

Mode = Literal["auto", "en", "hi", "hi-en"]
MIXED_PROMPT = "हिंदी को देवनागरी में और English terms in English लिखें।"


class RealtimeError(Exception):
    pass


@dataclass
class InferenceResult:
    text: str
    processing_seconds: float
    detected_language: str | None = None
    language_probability: float | None = None


class RealtimeTranscriber:
    """One lazy model and one bounded inference lane shared by live sessions."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._model: object | None = None
        self._lock = threading.Lock()
        self._slots = threading.BoundedSemaphore(self.settings.max_concurrent_transcriptions)

    def _model_instance(self) -> object:
        with self._lock:
            if self._model is None:
                from faster_whisper import WhisperModel
                self._model = WhisperModel(self.settings.whisper_model, device=self.settings.whisper_device, compute_type=self.settings.whisper_compute_type)
        return self._model

    def infer(self, samples: np.ndarray, mode: Mode, final: bool = False) -> InferenceResult:
        if not len(samples):
            return InferenceResult("", 0.0)
        started = time.perf_counter()
        language = None if mode == "auto" else ("hi" if mode == "hi-en" else mode)
        try:
            with self._slots:
                segments, info = self._model_instance().transcribe(
                    samples.astype(np.float32), task="transcribe", language=language,
                    multilingual=mode in {"auto", "hi-en"}, initial_prompt=MIXED_PROMPT if mode == "hi-en" else None,
                    vad_filter=True, beam_size=5, temperature=0.0, condition_on_previous_text=False,
                )
                text = " ".join(segment.text.strip() for segment in segments).strip()
                detected = str(info.language) if mode == "auto" else None
                probability = float(info.language_probability) if mode == "auto" else None
                # Keep partial latency low. The complete final recording gets one bounded
                # Hindi candidate pass only for Arabic-script auto output with Hindi evidence.
                if final and mode == "auto" and has_hindi_candidate_evidence(str(info.language), getattr(info, "all_language_probs", None), detect_output_script(text)):
                    retry_segments, retry_info = self._model_instance().transcribe(samples.astype(np.float32), task="transcribe", language="hi", multilingual=False, initial_prompt=None, vad_filter=True, beam_size=3, temperature=0.2, condition_on_previous_text=False)
                    retry_text = " ".join(segment.text.strip() for segment in retry_segments).strip()
                    if detect_output_script(retry_text) == "Devanagari" and not assess_transcription(retry_text).severe_repetition:
                        text, detected, probability = retry_text, "hi", None
                return InferenceResult(text, time.perf_counter() - started, detected, probability)
        except Exception as exc:
            raise RealtimeError("Speech recognition failed.") from exc


_transcriber: RealtimeTranscriber | None = None
_transcriber_lock = threading.Lock()


def get_realtime_transcriber() -> RealtimeTranscriber:
    global _transcriber
    with _transcriber_lock:
        if _transcriber is None:
            _transcriber = RealtimeTranscriber()
    return _transcriber


def pcm16_to_mono_16k(data: bytes, sample_rate: int, channels: int) -> np.ndarray:
    if sample_rate < 8000 or sample_rate > 96000 or channels not in {1, 2} or len(data) % (2 * channels):
        raise RealtimeError("Invalid PCM audio frame.")
    audio = np.frombuffer(data, dtype="<i2").astype(np.float32) / 32768.0
    if channels == 2:
        audio = audio.reshape(-1, 2).mean(axis=1)
    if sample_rate == 16000:
        return audio
    source = np.arange(len(audio), dtype=np.float64)
    target = np.linspace(0, max(0, len(audio) - 1), round(len(audio) * 16000 / sample_rate))
    return np.interp(target, source, audio).astype(np.float32)


def append_without_overlap(final_text: str, candidate: str) -> str:
    """Preserve finalized text while removing word overlap from a new window."""
    old, new = final_text.split(), candidate.split()
    maximum = min(len(old), len(new), 30)
    for size in range(maximum, 0, -1):
        if [word.casefold() for word in old[-size:]] == [word.casefold() for word in new[:size]]:
            new = new[size:]
            break
    return " ".join(old + new).strip()
