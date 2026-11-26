import numpy as np
import pytest

from app.services.realtime import RealtimeError, append_without_overlap, pcm16_to_mono_16k


def test_pcm_audio_is_resampled_to_mono_16k() -> None:
    samples = (np.zeros(4_800, dtype="<i2")).tobytes()
    assert len(pcm16_to_mono_16k(samples, 48_000, 1)) == 1_600


def test_invalid_pcm_frame_is_rejected() -> None:
    with pytest.raises(RealtimeError):
        pcm16_to_mono_16k(b"x", 48_000, 1)


def test_overlap_reconciliation_does_not_duplicate_words() -> None:
    assert append_without_overlap("Hello everyone आज हम", "आज हम Python के बारे में") == "Hello everyone आज हम Python के बारे में"
