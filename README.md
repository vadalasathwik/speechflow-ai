# SpeechFlow AI

SpeechFlow AI is an open-source Faster-Whisper speech-to-text application for the Procucev AI Tech Hiring Assignment. The supported recognition scope is English, Hindi, and Hindi-English code-switching. This iteration provides batch transcription from a browser microphone recording or an uploaded audio file; it is not WebSocket streaming.

The wider assignment also calls for relational persistence, a transcription dashboard with CRUD, GitHub publication, and cloud deployment. Those are not implemented in this scope-correction task and must be completed separately.

## Architecture

```text
frontend/  Next.js App Router + TypeScript + Tailwind CSS
     | HTTP (batch transcription)
backend/   FastAPI + Pydantic + SQLAlchemy 2.0 + Alembic
     |
PostgreSQL Docker Compose service
```

## Prerequisites

- Node.js 20.9+
- Homebrew Python 3.13 (verified on Apple Silicon; Python 3.15 currently lacks a compatible PyAV wheel in this setup)
- Docker Desktop (local PostgreSQL)

## Local setup

Create local config files:

```bash
cp .env.example .env
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
```

Start PostgreSQL:

```bash
docker compose up -d postgres
```

Run the backend from `backend/`:

```bash
/opt/homebrew/bin/python3.13 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
uvicorn app.main:app --reload --port 8000
```

Health check: [http://localhost:8000/api/health](http://localhost:8000/api/health). Apply future schema changes with `alembic upgrade head`.

Run the frontend from `frontend/`:

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

If Python 3.13 is absent, install it with Homebrew, then recreate the project environment:

```bash
brew install python@3.13
rm -rf backend/.venv
/opt/homebrew/bin/python3.13 -m venv backend/.venv
backend/.venv/bin/pip install -e 'backend[dev]'
```

## Environment variables

| File | Purpose |
| --- | --- |
| `.env` | Docker Compose PostgreSQL defaults |
| `backend/.env` | API settings, CORS origins, database URL |
| `frontend/.env.local` | Browser-visible backend base URL |

`ALLOWED_ORIGINS` is a JSON list, e.g. `ALLOWED_ORIGINS=["http://localhost:3000"]`.

Backend speech settings are configured in `backend/.env`. `WHISPER_MODEL` accepts either a Faster-Whisper model name (for example, `small`) or an absolute directory containing a locally downloaded CTranslate2 model. Keep local model directories outside the repository and set their path only in the ignored local `backend/.env`. The current development setup uses the locally downloaded `large-v3-turbo` model with `WHISPER_DEVICE=cpu` and `WHISPER_COMPUTE_TYPE=int8`; deployments can select a smaller model instead.

Set `NEXT_PUBLIC_MAX_AUDIO_DURATION_SECONDS=120` in `frontend/.env.local` to match the backend recording limit.

## Transcription API

`POST /api/transcribe` accepts `multipart/form-data` with a `file` and optional `language`: `auto`, `en`, `hi`, or `hi-en`. Telugu, Tamil, and Urdu are intentionally not exposed by the API or UI. WAV, MP3, M4A, MP4, and WebM are supported. Audio is byte-limited while it is read, decoded through PyAV, and removed after the response.

```bash
curl -X POST http://localhost:8000/api/transcribe \
  -F 'file=@sample.webm' \
  -F 'language=auto'
```

```json
{
  "text": "Hello everyone, आज हम Python के बारे में बात करेंगे।",
  "language": "hi",
  "language_probability": 0.92,
  "model": "small",
  "recognition_mode": "hi-en",
  "conditioned_language": "hi",
  "duration_seconds": 4.8,
  "processing_time_seconds": 1.37,
  "segments": [{"start": 0.0, "end": 4.8, "text": "Hello everyone, आज हम Python के बारे में बात करेंगे।"}]
}
```

The response above is illustrative only, not a measured result. `recognition_mode` is the UI selection, `conditioned_language` is the language supplied to Faster-Whisper (`null` for Auto Detect), and `language` is Faster-Whisper's detected language. A forced-language probability is conditioning metadata, not an independent detection confidence. Whisper language detection is a dominant-language estimate: it does not identify every language used in a code-switched recording.

## Decoding and model guidance

- Faster-Whisper 1.2.1 is installed. Its supported `WhisperModel.transcribe` interface accepts `task="transcribe"`, `language`, `initial_prompt`, and `multilingual`. It has no Hindi-English composite language code.
- Every request uses `task="transcribe"`; no translation task is used. Hindi-English mixed mode conditions the first pass as Hindi, uses a generic instruction to retain English terms in English, and enables the supported `multilingual=True` option so later audio windows can be language-detected. The generic instruction is not an acceptance reference sentence.
- The model is initialized lazily once per backend process, inference is bounded to one job by default, and CPU `int8` preserves Apple Silicon compatibility. Keep `WHISPER_MODEL` configurable through `backend/.env`.
- Provisional deployment choice: **Small** offers the safer latency and memory profile for a CPU deployment. **Large-v3 Turbo** is the candidate for higher Hindi-English quality when the deployment can supply materially more CPU/RAM. Do not promote Turbo as the default until the required recordings establish a measurable accuracy benefit.

## Required benchmark evidence

No benchmark result is reported yet. Local recordings exist but are not confirmed against the assignment sentences, so using them would fabricate accuracy evidence. Obtain a clearly labeled human recording for each sentence below (one speaker/environment per comparison), then run each clip with both existing models, `small` and `large-v3-turbo`:

- English: “Hello, I am developing a real-time speech recognition application.”
- Hindi: “नमस्ते, आज हम आर्टिफिशियल इंटेलिजेंस के बारे में बात करेंगे।”
- Hindi-English mixed: “Hello everyone, आज हम Python और Artificial Intelligence के बारे में बात करेंगे।”
- Hindi-English mixed: “आज हमारी meeting में हम project requirements और deployment के बारे में discuss करेंगे।”

Use the supplied benchmark utility with each confirmed file. It emits the actual transcript, processing time, real-time factor, decoded-audio diagnostics, and peak RSS; calculate WER only against that recording's exact reference. The reference text must never be supplied as an inference hint.

```bash
# backend/, with the existing local model paths supplied through arguments
.venv/bin/python scripts/benchmark_whisper.py /path/to/existing-small en /path/to/confirmed-english.wav
.venv/bin/python scripts/benchmark_whisper.py /path/to/existing-small hi /path/to/confirmed-hindi.wav
.venv/bin/python scripts/benchmark_whisper.py /path/to/existing-small hi-en /path/to/confirmed-mixed.wav
.venv/bin/python scripts/benchmark_whisper.py /path/to/large-v3-turbo hi-en /path/to/confirmed-mixed.wav
```

## Browser microphone recording

Select **Record Audio**, grant microphone permission, and use Start/Stop to produce an audio preview. Chrome normally records WebM/Opus while Safari normally records MP4/AAC. SpeechFlow detects a supported browser MIME type and preserves its true file extension. It uses batch uploads, not live streaming, and never uses the browser Web Speech API.

The evaluation panel contains only the four assignment references. Selecting one changes the recognition mode and compares it after real transcription; its reference text is never sent to Faster-Whisper. Its optional Word Error Rate lowercases text, removes punctuation, and applies word-level edit distance. It is not a universal accuracy score: punctuation, transliteration, and different scripts can affect the comparison. Recording and transcription diagnostics are tucked into expandable sections.

## Verification

```bash
# frontend/
npm run lint
npx tsc --noEmit

# backend/ (activated virtual environment)
pytest
```

## Current boundary

Batch recognition, local playback/download, audio validation, timestamped segments, repetition checks, and safe environment configuration are implemented. WebSockets, microphone streaming, database transcript CRUD, deployment, and GitHub publication remain outside this task.
