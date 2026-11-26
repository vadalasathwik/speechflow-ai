"""Benchmark one Faster-Whisper configuration in an isolated process."""
import argparse
import json
import resource
import time

import av
from faster_whisper import WhisperModel


def audio_diagnostics(path: str) -> dict[str, object]:
    container = av.open(path)
    stream = next(item for item in container.streams if item.type == "audio")
    samples = 0
    peak = 0.0
    squares = 0.0
    clipped = 0
    for frame in container.decode(stream):
        data = frame.to_ndarray().astype("float32")
        scale = 32768.0 if data.max(initial=0) > 2 else 1.0
        data /= scale
        samples += data.size
        peak = max(peak, float(abs(data).max(initial=0)))
        squares += float((data * data).sum())
        clipped += int((abs(data) >= 0.999).sum())
    container.close()
    return {"container": container.format.name, "codec": stream.codec_context.name, "sample_rate": stream.rate, "channels": stream.channels, "samples": samples, "duration": samples / stream.rate / stream.channels, "peak": peak, "rms": (squares / samples) ** 0.5, "clipping_percent": clipped / samples * 100}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model")
    parser.add_argument("language", choices=["auto", "en", "hi", "hi-en"])
    parser.add_argument("audio")
    args = parser.parse_args()
    diagnostics = audio_diagnostics(args.audio)
    started = time.perf_counter()
    model = WhisperModel(args.model, device="cpu", compute_type="int8")
    initialized = time.perf_counter() - started
    started = time.perf_counter()
    selected_language = None if args.language == "auto" else ("hi" if args.language == "hi-en" else args.language)
    initial_prompt = "हिंदी को देवनागरी में और English terms in English लिखें।" if args.language == "hi-en" else None
    segments, info = model.transcribe(args.audio, task="transcribe", language=selected_language, multilingual=args.language in {"auto", "hi-en"}, initial_prompt=initial_prompt, vad_filter=True, beam_size=5, temperature=0.0, condition_on_previous_text=False)
    segment_list = [{"start": segment.start, "end": segment.end, "text": segment.text.strip()} for segment in segments]
    processing = time.perf_counter() - started
    result = {"model": args.model, "mode": args.language, "init_seconds": initialized, "processing_seconds": processing, "real_time_factor": processing / diagnostics["duration"], "language": info.language, "language_probability": info.language_probability, "text": " ".join(item["text"] for item in segment_list).strip(), "segments": segment_list, "audio": diagnostics, "peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024)}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
