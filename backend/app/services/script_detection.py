from collections import Counter

SCRIPT_RANGES = {
    "Devanagari": ((0x0900, 0x097F),),
    "Arabic": ((0x0600, 0x06FF),),
    "Latin": ((0x0041, 0x005A), (0x0061, 0x007A)),
}
EXPECTED_SCRIPTS = {"hi": "Devanagari", "en": "Latin"}


def detect_output_script(text: str) -> str:
    counts = Counter()
    for character in text:
        point = ord(character)
        for script, ranges in SCRIPT_RANGES.items():
            if any(start <= point <= end for start, end in ranges):
                counts[script] += 1
                break
    return counts.most_common(1)[0][0] if counts else "Unknown"


def script_warning(language: str, script: str, recognition_mode: str) -> str | None:
    if recognition_mode == "hi-en":
        return None if script in {"Devanagari", "Latin", "Unknown"} else "Mixed Hindi-English mode expected Devanagari and/or Latin output, but another script dominates."
    expected = EXPECTED_SCRIPTS.get(language)
    if expected and script not in {expected, "Unknown"}:
        return f"Detected language '{language}' usually uses {expected}, but {script} dominates the transcription output."
    return None


def has_hindi_candidate_evidence(language: str, all_language_probs: object, script: str) -> bool:
    """Allow one Hindi retry only for unsupported Arabic-script auto output with Hindi evidence."""
    if script != "Arabic" or language not in {"hi", "ur"}:
        return False
    try:
        probabilities = dict(all_language_probs or [])
        hindi = float(probabilities.get("hi", 0.0))
        detected = float(probabilities.get(language, 0.0))
    except (TypeError, ValueError):
        return language == "hi"
    return language == "hi" or (hindi >= 0.15 and hindi >= detected - 0.25)
