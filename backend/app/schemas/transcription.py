from pydantic import BaseModel, Field


class TranscriptionSegment(BaseModel):
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    text: str


class TranscriptionResponse(BaseModel):
    text: str
    language: str
    language_probability: float = Field(ge=0, le=1)
    duration_seconds: float = Field(ge=0)
    processing_time_seconds: float = Field(ge=0)
    real_time_factor: float = Field(ge=0)
    model: str
    recognition_mode: str
    conditioned_language: str | None = None
    output_script: str
    script_warning: str | None = None
    quality_warning: str | None = None
    retry_performed: bool = False
    original_text: str | None = None
    segments: list[TranscriptionSegment]
