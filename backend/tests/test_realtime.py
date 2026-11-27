import numpy as np
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.config import Settings
from app.main import app
from app.services.realtime import RealtimeError, append_without_overlap, pcm16_to_mono_16k


def test_pcm_audio_is_resampled_to_mono_16k() -> None:
    samples = (np.zeros(4_800, dtype="<i2")).tobytes()
    assert len(pcm16_to_mono_16k(samples, 48_000, 1)) == 1_600


def test_invalid_pcm_frame_is_rejected() -> None:
    with pytest.raises(RealtimeError):
        pcm16_to_mono_16k(b"x", 48_000, 1)


def test_overlap_reconciliation_does_not_duplicate_words() -> None:
    assert append_without_overlap("Hello everyone आज हम", "आज हम Python के बारे में") == "Hello everyone आज हम Python के बारे में"


def test_realtime_websocket_accepts_the_explicit_caddy_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.api.routes.realtime.get_settings", lambda: Settings(allowed_origins=["http://localhost:8080"]))
    with TestClient(app) as client:
        with client.websocket_connect("/ws/transcribe", headers={"origin": "http://localhost:8080"}) as websocket:
            websocket.send_json({"type": "start", "sample_rate": 16_000, "channels": 1, "pcm_format": "s16le"})
            assert websocket.receive_json()["type"] == "ready"


def test_realtime_websocket_rejects_an_unlisted_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.api.routes.realtime.get_settings", lambda: Settings(allowed_origins=["http://localhost:8080"]))
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as error:
            with client.websocket_connect("/ws/transcribe", headers={"origin": "https://attacker.example"}):
                pass
        assert error.value.code == 1008
