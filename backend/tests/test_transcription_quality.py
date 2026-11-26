from app.services.transcription_quality import assess_transcription, graphemes


def test_flags_repeated_grapheme_loop() -> None:
    assessment = assess_transcription("कककककककककककक")
    assert assessment.severe_repetition


def test_flags_repeated_english_phrase() -> None:
    assert assess_transcription("hello hello hello hello hello hello").severe_repetition


def test_does_not_split_indic_combining_marks() -> None:
    assert len(graphemes("कि")) == 1
    assert not assess_transcription("नमस्ते आज हम बात करेंगे").severe_repetition
