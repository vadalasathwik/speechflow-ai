import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class TranscriptionCreate(BaseModel):
    title: str = Field(max_length=255)
    text: str = Field(min_length=1)
    detected_language: str | None = Field(default=None, max_length=16)
    source_type: Literal["recording", "upload"]
    duration_seconds: float | None = Field(default=None, ge=0)
    model_name: str | None = Field(default=None, max_length=255)

    @field_validator("title", "text")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value


class TranscriptionUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    text: str | None = Field(default=None, min_length=1)

    @field_validator("title", "text")
    @classmethod
    def fields_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("must not be blank")
        return value

    @model_validator(mode="after")
    def has_update(self) -> "TranscriptionUpdate":
        if self.title is None and self.text is None:
            raise ValueError("provide a title or text to update")
        return self


class TranscriptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    title: str
    text: str
    detected_language: str | None
    source_type: str
    duration_seconds: float | None
    model_name: str | None
    created_at: datetime
    updated_at: datetime


class TranscriptionPage(BaseModel):
    items: list[TranscriptionRead]
    total: int
    page: int
    page_size: int
