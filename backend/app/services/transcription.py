import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from app.core.config import Settings, get_settings
from app.services.script_detection import detect_output_script, has_hindi_candidate_evidence, script_warning
from app.services.transcription_quality import assess_transcription

logger = logging.getLogger(__name__)

LanguageSelection = Literal["auto", "en", "hi", "hi-en"]
SUPPORTED_LANGUAGES = {"auto", "en", "hi", "hi-en"}
# This is a generic decoding instruction, not an evaluation reference sentence.
HINDI_ENGLISH_PROMPT = "हिंदी को देवनागरी में और English terms in English लिखें।"


class TranscriptionError(Exception):
    """Base error raised for safe transcription API failures."""


class InvalidAudioError(TranscriptionError):
    """The uploaded bytes could not be decoded as supported audio."""


class ModelInitializationError(TranscriptionError):
    """The local Faster-Whisper model could not be initialized."""


class InferenceError(TranscriptionError):
    """Faster-Whisper could not transcribe the supplied audio."""


@dataclass(frozen=True)
class SegmentResult:
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class TranscriptionResult:
    text: str
    language: str
    language_probability: float
    duration_seconds: float
    processing_time_seconds: float
    segments: list[SegmentResult]
    model: str = "base"
    recognition_mode: str = "auto"
    conditioned_language: str | None = None
    output_script: str = "Unknown"
    script_warning: str | None = None
    original_text: str | None = None
    quality_warning: str | None = None
    retry_performed: bool = False


def get_audio_duration(path: Path) -> float:
    """Decode audio with PyAV and return its measured duration in seconds."""
    try:
        import av
    except ImportError as exc:
        raise InvalidAudioError("Audio decoding is unavailable.") from exc

    try:
        with av.open(str(path)) as container:
            audio_streams = [item for item in container.streams if item.type == "audio"]
            stream = audio_streams[0] if audio_streams else None
            if stream is None:
                raise InvalidAudioError("No audio stream was found.")
            decoded_samples = 0
            decoded_duration = 0.0
            for frame in container.decode(stream):
                if frame.sample_rate <= 0:
                    continue
                decoded_samples += frame.samples
                decoded_duration += frame.samples / frame.sample_rate
            if decoded_samples == 0:
                raise InvalidAudioError("No decodable audio samples were found.")
            if stream.duration is not None and stream.time_base is not None:
                metadata_duration = float(stream.duration * stream.time_base)
            elif container.duration is not None:
                metadata_duration = float(container.duration / av.time_base)
            else:
                metadata_duration = None
            # Browser-recorded WebM often omits or misreports container duration; decoded frames are authoritative.
            duration = decoded_duration
            logger.info(
                "Decoded audio diagnostics: container=%s codec=%s audio_streams=%d metadata_duration=%s decoded_samples=%d decoded_duration=%.3f",
                container.format.name,
                stream.codec_context.name,
                len(audio_streams),
                metadata_duration,
                decoded_samples,
                decoded_duration,
            )
    except InvalidAudioError:
        raise
    except (av.FFmpegError, OSError, ValueError) as exc:
        logger.warning("Audio decoding failed: exception=%s message=%s", type(exc).__name__, str(exc))
        raise InvalidAudioError("The uploaded file is not valid audio.") from exc
    if duration <= 0:
        raise InvalidAudioError("The uploaded audio is empty.")
    return duration


class FasterWhisperTranscriptionService:
    """Thread-safe, lazily initialized adapter around Faster-Whisper."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._model: object | None = None
        self._model_lock = threading.Lock()
        self._inference_slots = threading.BoundedSemaphore(self.settings.max_concurrent_transcriptions)

    def _get_model(self) -> object:
        if self._model is not None:
            return self._model
        with self._model_lock:
            if self._model is None:
                try:
                    from faster_whisper import WhisperModel

                    self._model = WhisperModel(
                        self.settings.whisper_model,
                        device=self.settings.whisper_device,
                        compute_type=self.settings.whisper_compute_type,
                    )
                except Exception as exc:
                    raise ModelInitializationError("Speech recognition model is unavailable.") from exc
        return self._model

    def _run_transcription(self, model: object, audio_path: Path, language: str | None, initial_prompt: str | None, multilingual: bool, beam_size: int | None = None, temperature: float | None = None):
        return model.transcribe(
            str(audio_path), task="transcribe", language=language,
            multilingual=multilingual,
            vad_filter=self.settings.whisper_vad_filter,
            beam_size=beam_size or self.settings.whisper_beam_size,
            temperature=self.settings.whisper_temperature if temperature is None else temperature,
            condition_on_previous_text=self.settings.whisper_condition_on_previous_text,
            initial_prompt=initial_prompt,
        )

    def transcribe(self, audio_path: Path, language: LanguageSelection | None = None) -> TranscriptionResult:
        """Run blocking inference. Call this from a worker thread in web handlers."""
        started = time.perf_counter()
        try:
            model = self._get_model()
            requested_language = language or self.settings.whisper_language
            recognition_mode = requested_language
            selected_language = None if requested_language == "auto" else ("hi" if requested_language == "hi-en" else requested_language)
            initial_prompt = HINDI_ENGLISH_PROMPT if requested_language == "hi-en" else None
            multilingual = requested_language in {"auto", "hi-en"}
            with self._inference_slots:
                segments, info = self._run_transcription(model, audio_path, selected_language, initial_prompt, multilingual)
                result_segments = [
                    SegmentResult(start=float(segment.start), end=float(segment.end), text=segment.text.strip())
                    for segment in segments
                ]
                text = " ".join(item.text for item in result_segments).strip()
                output_script = detect_output_script(text)
                warning = script_warning(str(info.language), output_script, recognition_mode)
                quality = assess_transcription(text)
                original_text = None
                retry_performed = False
                # Arabic-derived output is retried as Hindi only when Whisper itself detected
                # Hindi. This repairs a decoder script mismatch without relabelling Urdu audio.
                hindi_script_mismatch = requested_language == "auto" and has_hindi_candidate_evidence(str(info.language), getattr(info, "all_language_probs", None), output_script)
                if (warning or quality.severe_repetition or hindi_script_mismatch) and self.settings.whisper_enable_script_retry:
                    retry_performed = True
                    retry_language = "hi" if hindi_script_mismatch else selected_language or str(info.language)
                    retry_prompt = HINDI_ENGLISH_PROMPT if requested_language == "hi-en" else None
                    retry_segments, retry_info = self._run_transcription(model, audio_path, retry_language, retry_prompt, multilingual, beam_size=3, temperature=0.2)
                    retry_results = [SegmentResult(start=float(item.start), end=float(item.end), text=item.text.strip()) for item in retry_segments]
                    retry_text = " ".join(item.text for item in retry_results).strip()
                    retry_script = detect_output_script(retry_text)
                    retry_quality = assess_transcription(retry_text)
                    retry_is_devanagari = hindi_script_mismatch and retry_script == "Devanagari" and not retry_quality.severe_repetition
                    if retry_is_devanagari or (quality.severe_repetition and not retry_quality.severe_repetition) or (warning and not script_warning(str(retry_info.language), retry_script, recognition_mode)):
                        original_text = text
                        result_segments, text, output_script, warning, info, quality = retry_results, retry_text, retry_script, script_warning(str(retry_info.language), retry_script, recognition_mode), retry_info, retry_quality
        except ModelInitializationError:
            raise
        except Exception as exc:
            raise InferenceError("Speech recognition failed.") from exc
        return TranscriptionResult(
            text=text,
            language=str(info.language),
            language_probability=float(info.language_probability),
            duration_seconds=get_audio_duration(audio_path),
            processing_time_seconds=round(time.perf_counter() - started, 3),
            segments=result_segments,
            model=self.settings.whisper_model,
            recognition_mode=recognition_mode,
            conditioned_language=selected_language,
            output_script=output_script,
            script_warning=warning,
            original_text=original_text,
            quality_warning=quality.warning,
            retry_performed=retry_performed,
        )


_service: FasterWhisperTranscriptionService | None = None
_service_lock = threading.Lock()


def get_transcription_service() -> FasterWhisperTranscriptionService:
    global _service
    if _service is None:
        with _service_lock:
            if _service is None:
                _service = FasterWhisperTranscriptionService()
    return _service
