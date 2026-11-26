from app.services.script_detection import detect_output_script, script_warning


def test_detects_indic_and_latin_scripts() -> None:
    assert detect_output_script("नमस्ते") == "Devanagari"
    assert detect_output_script("hello") == "Latin"


def test_warns_when_detected_language_and_script_disagree() -> None:
    assert script_warning("hi", "Latin", "auto")
    assert script_warning("en", "Devanagari", "en")
    assert script_warning("hi", "Devanagari", "hi") is None


def test_mixed_hindi_english_allows_devanagari_and_latin() -> None:
    assert script_warning("hi", "Devanagari", "hi-en") is None
    assert script_warning("hi", "Latin", "hi-en") is None
