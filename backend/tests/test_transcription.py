from pathlib import Path
from types import SimpleNamespace
import wave

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.main import app
from app.services.transcription import (
    InferenceError,
    InvalidAudioError,
    ModelInitializationError,
    SegmentResult,
    TranscriptionResult,
    get_transcription_service,
    get_audio_duration,
    FasterWhisperTranscriptionService,
)


class FakeService:
    def __init__(self, result: TranscriptionResult | Exception) -> None:
        self.result = result
        self.paths: list[Path] = []

    def transcribe(self, path: Path, language: str) -> TranscriptionResult:
        self.paths.append(path)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    settings = Settings(max_audio_size_mb=1, max_audio_duration_seconds=120)
    app.dependency_overrides[get_settings] = lambda: settings
    monkeypatch.setattr("app.api.routes.transcription.get_audio_duration", lambda path: 2.5)
    yield TestClient(app)
    app.dependency_overrides.clear()


def upload(client: TestClient, name: str = "sample.wav", payload: bytes = b"audio", language: str = "auto"):
    return client.post("/api/transcribe", files={"file": (name, payload, "audio/wav")}, data={"language": language})


def override_service(service: FakeService) -> None:
    app.dependency_overrides[get_transcription_service] = lambda: service


def test_successful_transcription_and_response_schema(client: TestClient) -> None:
    override_service(FakeService(TranscriptionResult(
        text="Hello आज",
        language="hi",
        language_probability=0.92,
        duration_seconds=2.5,
        processing_time_seconds=0.42,
        segments=[SegmentResult(start=0, end=2.5, text="Hello आज")],
    )))

    response = upload(client)

    assert response.status_code == 200
    assert response.json() == {
        "text": "Hello आज", "language": "hi", "language_probability": 0.92,
        "duration_seconds": 2.5, "processing_time_seconds": 0.42,
        "real_time_factor": 0.168, "model": "base", "recognition_mode": "auto", "conditioned_language": None,
        "output_script": "Unknown", "script_warning": None, "original_text": None,
        "quality_warning": None, "retry_performed": False,
        "segments": [{"start": 0.0, "end": 2.5, "text": "Hello आज"}],
    }


def test_missing_file_is_rejected(client: TestClient) -> None:
    response = client.post("/api/transcribe", data={"language": "auto"})
    assert response.status_code == 422
    assert response.json()["detail"][0] == {"type": "missing", "loc": ["body", "file"], "msg": "Field required", "input": None}


def test_wrong_multipart_field_is_rejected_as_missing_file(client: TestClient) -> None:
    response = client.post("/api/transcribe", files={"audio": ("sample.wav", b"audio", "audio/wav")}, data={"language": "auto"})
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "file"]


def test_cors_headers_are_returned_for_validation_errors(client: TestClient) -> None:
    response = client.post("/api/transcribe", headers={"Origin": "http://localhost:3000"}, data={"language": "auto"})
    assert response.status_code == 422
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_empty_file_is_rejected(client: TestClient) -> None:
    override_service(FakeService(AssertionError("must not run")))
    assert upload(client, payload=b"").status_code == 422


def test_unsupported_format_is_rejected(client: TestClient) -> None:
    override_service(FakeService(AssertionError("must not run")))
    assert upload(client, name="sample.txt").status_code == 415


def test_browser_mp4_format_is_accepted(client: TestClient) -> None:
    override_service(FakeService(TranscriptionResult("done", "en", 0.9, 2.5, 0.1, [])))
    assert upload(client, name="recording.mp4").status_code == 200


def test_invalid_language_is_rejected(client: TestClient) -> None:
    override_service(FakeService(AssertionError("must not run")))
    assert upload(client, language="fr").status_code == 422


@pytest.mark.parametrize("language", ["te", "ta", "ur"])
def test_out_of_scope_language_is_rejected(client: TestClient, language: str) -> None:
    override_service(FakeService(AssertionError("must not run")))
    assert upload(client, language=language).status_code == 422


def test_hindi_english_mixed_mode_is_accepted(client: TestClient) -> None:
    override_service(FakeService(TranscriptionResult("Hello आज", "hi", 0.9, 2.5, 0.1, [])))
    assert upload(client, language="hi-en").status_code == 200


class CapturingModel:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def transcribe(self, _path: str, **kwargs: object):
        self.calls.append(kwargs)
        return [SimpleNamespace(start=0, end=1, text="Hello नमस्ते")], SimpleNamespace(language="hi", language_probability=1.0)


def test_mixed_mode_uses_supported_multilingual_transcribe_options(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    model = CapturingModel()
    service = FasterWhisperTranscriptionService(Settings(whisper_enable_script_retry=False))
    service._model = model
    monkeypatch.setattr("app.services.transcription.get_audio_duration", lambda _path: 1.0)

    result = service.transcribe(tmp_path / "confirmed-mixed.wav", "hi-en")

    assert result.text == "Hello नमस्ते"
    assert model.calls == [{
        "task": "transcribe",
        "language": "hi",
        "multilingual": True,
        "vad_filter": True,
        "beam_size": 5,
        "temperature": 0.0,
        "condition_on_previous_text": False,
        "initial_prompt": "हिंदी को देवनागरी में और English terms in English लिखें।",
    }]


def test_oversized_upload_is_rejected_while_streaming(client: TestClient) -> None:
    override_service(FakeService(AssertionError("must not run")))
    assert upload(client, payload=b"a" * (1024 * 1024 + 1)).status_code == 413


def test_corrupted_audio_is_rejected(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    override_service(FakeService(AssertionError("must not run")))
    monkeypatch.setattr("app.api.routes.transcription.get_audio_duration", lambda path: (_ for _ in ()).throw(InvalidAudioError()))
    assert upload(client).status_code == 422


def test_excessive_duration_is_rejected(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    override_service(FakeService(AssertionError("must not run")))
    monkeypatch.setattr("app.api.routes.transcription.get_audio_duration", lambda path: 121.0)
    assert upload(client).status_code == 422


@pytest.mark.parametrize("error,status_code", [(ModelInitializationError(), 503), (InferenceError(), 500)])
def test_service_errors_are_safe(client: TestClient, error: Exception, status_code: int) -> None:
    override_service(FakeService(error))
    response = upload(client)
    assert response.status_code == status_code
    assert "Traceback" not in response.text


def test_temporary_file_is_deleted_after_transcription(client: TestClient) -> None:
    service = FakeService(TranscriptionResult("done", "en", 0.9, 2.5, 0.1, []))
    override_service(service)

    assert upload(client).status_code == 200
    assert service.paths and not service.paths[0].exists()


def test_pyav_measures_duration_from_decoded_audio_samples(tmp_path: Path) -> None:
    audio_path = tmp_path / "sample.wav"
    with wave.open(str(audio_path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16_000)
        output.writeframes(b"\x00\x00" * 16_000)

    assert get_audio_duration(audio_path) == pytest.approx(1.0, abs=0.02)
