import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class QualityAssessment:
    severe_repetition: bool
    warning: str | None
    compression_ratio: float


def graphemes(text: str) -> list[str]:
    groups: list[str] = []
    for character in text:
        if groups and (unicodedata.combining(character) or unicodedata.category(character).startswith("M")):
            groups[-1] += character
        else:
            groups.append(character)
    return groups


def assess_transcription(text: str) -> QualityAssessment:
    units = [unit for unit in graphemes(text) if not unit.isspace()]
    if not units:
        return QualityAssessment(False, None, 1.0)
    longest_run = 1
    run = 1
    for previous, current in zip(units, units[1:]):
        run = run + 1 if current == previous else 1
        longest_run = max(longest_run, run)
    words = re.findall(r"[^\s]+", text.casefold())
    repeated_words = bool(words) and max(words.count(word) for word in set(words)) >= 5
    ratio = len(units) / max(1, len(set(units)))
    repeated_sequence = False
    for width in range(1, min(5, len(units) // 4 + 1)):
        for index in range(len(units) - width * 4 + 1):
            pattern = units[index:index + width]
            if all(units[index + offset * width:index + (offset + 1) * width] == pattern for offset in range(1, 4)):
                repeated_sequence = True
                break
        if repeated_sequence:
            break
    severe = longest_run >= 8 or repeated_words or repeated_sequence or (len(units) >= 20 and ratio >= 5)
    warning = "The transcription contains severe repetitive patterns and may be unreliable." if severe else None
    return QualityAssessment(severe, warning, ratio)
