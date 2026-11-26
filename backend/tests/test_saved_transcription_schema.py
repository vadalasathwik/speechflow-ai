import pytest
from pydantic import ValidationError

from app.schemas.saved_transcription import TranscriptionCreate, TranscriptionUpdate


def test_create_contract_preserves_hindi_and_mixed_unicode() -> None:
    record = TranscriptionCreate(title="Hindi", text="नमस्ते, आज हमारी meeting है", source_type="recording", detected_language="hi")
    assert record.text == "नमस्ते, आज हमारी meeting है"


@pytest.mark.parametrize("payload", [{"title": " ", "text": "text", "source_type": "upload"}, {"title": "Title", "text": "", "source_type": "upload"}, {"title": "Title", "text": "text", "source_type": "other"}])
def test_create_contract_rejects_invalid_values(payload: dict[str, str]) -> None:
    with pytest.raises(ValidationError):
        TranscriptionCreate(**payload)


def test_update_contract_allows_partial_update_and_rejects_blank_text() -> None:
    assert TranscriptionUpdate(title="Renamed").title == "Renamed"
    with pytest.raises(ValidationError):
        TranscriptionUpdate(text=" ")
    with pytest.raises(ValidationError):
        TranscriptionUpdate()
