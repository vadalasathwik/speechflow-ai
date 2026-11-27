# SpeechFlow AI

SpeechFlow AI is an open-source Faster-Whisper speech-to-text application for the Procucev AI Tech Hiring Assignment. It automatically recognizes English, Hindi, and Hindi-English mixed speech, preserving the original spoken language. It provides buffered near-real-time WebSocket transcription and batch transcription for uploaded audio.

The wider assignment also calls for a transcription history dashboard, GitHub publication, and cloud deployment. Persistent PostgreSQL CRUD is implemented; the dashboard and deployment remain future phases.

## Architecture

```text
frontend/  Next.js App Router + TypeScript + Tailwind CSS
     | HTTP batch upload + WebSocket PCM streaming
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

Health check: [http://localhost:8000/api/health](http://localhost:8000/api/health). Apply the transcription schema before using the CRUD endpoints with `alembic upgrade head`.

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

### Neon PostgreSQL

For a Neon database, set `DATABASE_URL` only in the ignored `backend/.env` file. Use the SQLAlchemy Psycopg driver prefix and require TLS; obtain the host, database, user, and password from the Neon connection details.

```dotenv
DATABASE_URL=postgresql+psycopg://<user>:<password>@<neon-host>/<database>?sslmode=require&channel_binding=require
```

Never put a real connection string in `.env.example`, source control, browser environment variables, or client-side code. Verify and apply the schema against the configured database with:

```bash
cd backend
.venv/bin/alembic current
.venv/bin/alembic upgrade head
.venv/bin/alembic current
```

Backend speech settings are configured in `backend/.env`. `WHISPER_MODEL` accepts either a Faster-Whisper model name (for example, `small`) or an absolute directory containing a locally downloaded CTranslate2 model. Keep local model directories outside the repository and set their path only in the ignored local `backend/.env`. The current development setup uses the locally downloaded `large-v3-turbo` model with `WHISPER_DEVICE=cpu` and `WHISPER_COMPUTE_TYPE=int8`; deployments can select a smaller model instead.

Set `NEXT_PUBLIC_MAX_AUDIO_DURATION_SECONDS=120` in `frontend/.env.local` to match the backend recording limit.

## Transcription API

`POST /api/transcribe` accepts `multipart/form-data` with a `file`. SpeechFlow automatically detects English, Hindi, and Hindi-English mixed speech and transcribes the original spoken language; it does not translate. WAV, MP3, M4A, MP4, and WebM are supported. Audio is byte-limited while it is read, decoded through PyAV, and removed after the response.

```bash
curl -X POST http://localhost:8000/api/transcribe \
  -F 'file=@sample.webm' \
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

## Live transcription

The browser captures microphone PCM through an AudioWorklet and streams it to `ws://localhost:8000/ws/transcribe` (or `wss://` in production). The backend runs bounded, overlapping Faster-Whisper windows for provisional text, then transcribes the complete captured session once after Stop for the final result. Completed live recordings are retained in-browser as WAV for playback and download; uploads retain their original file for playback and download.

SpeechFlow uses `task="transcribe"` exclusively. It never automatically translates a transcript. A bounded Hindi corrective pass is used only when an automatic Arabic-script result has meaningful Hindi detection evidence and the candidate produces non-repetitive Devanagari text.

## Persistent transcriptions API

PostgreSQL stores finalized transcript text and metadata only; audio files are never persisted. Run migrations before starting the API:

```bash
cd backend
.venv/bin/alembic upgrade head
```

`POST /api/transcriptions` creates a record. `GET /api/transcriptions` lists newest-first records with `page`, `page_size` (maximum 100), optional `search`, and optional `language`. `GET`, `PATCH`, and `DELETE /api/transcriptions/{id}` retrieve, update title/text, and delete a UUID record respectively.

```bash
curl -X POST http://localhost:8000/api/transcriptions \
  -H 'content-type: application/json' \
  -d '{"title":"Hindi note","text":"नमस्ते","source_type":"recording","detected_language":"hi"}'
```

Before public deployment, add session or authenticated ownership to these endpoints. The current unauthenticated list/search API is appropriate only for local single-user development and must not be exposed as shared public history.

## Transcription history dashboard

The web app has two primary workspaces: **Transcribe** and **History**. The Transcribe workspace preserves the existing Record Audio and Upload Audio flow. Once a live session has finalized or an upload has completed, **Save Transcription** stores only the transcript and recognition metadata; browser audio remains available for playback/download but is never stored in PostgreSQL.

History uses the FastAPI CRUD API through `NEXT_PUBLIC_API_BASE_URL`, never a direct database connection. It provides newest-first cards, total count, debounced search, detected-language filtering, pagination, complete-text viewing, Unicode-safe copying, editing, and confirmed deletion. It handles loading, empty, no-results, and retryable network-error states. Historical audio playback is intentionally unavailable because audio is not persisted.

**Deployment blocker:** the API has no visitor ownership checks. Keep History local until Phase 6 adds an anonymous, secure, HttpOnly session identifier (or authentication) and filters every list/read/update/delete operation by that owner. Do not deploy the unrestricted history API publicly.

### Neon integration verification

On 2026-11-26, the migration and CRUD API were verified against a Neon PostgreSQL 18.7 database over TLS (`sslmode=require`), with UTF-8 encoding. The `transcriptions` table has the UUID primary key, required metadata columns, `timestamptz` timestamps, database checks, and the created-at/language indexes from migration `20261126_01`.

Live API verification created English, Hindi, and Hindi-English mixed records; confirmed exact Unicode preservation; verified newest-first pagination, search, language filtering, update, delete, invalid-input validation, and unknown-record `404` handling. A remaining test record was retrieved after a FastAPI restart to confirm persistence, then all verification records were deleted. Connection credentials are not documented or committed.

## Decoding and model guidance

- Faster-Whisper 1.2.1 is installed. Its supported `WhisperModel.transcribe` interface accepts `task="transcribe"`, `language`, `initial_prompt`, and `multilingual`. It has no Hindi-English composite language code.
- Every request uses `task="transcribe"`; no translation task is used. Automatic multilingual decoding uses Faster-Whisper's supported `multilingual=True` option and does not force a Hindi or English language code. The generic mixed-language prompt is not an acceptance reference sentence.
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

Select **Record Audio**, grant microphone permission, and use Start/Stop to produce an audio preview. Chrome normally records WebM/Opus while Safari normally records MP4/AAC. SpeechFlow detects a supported browser MIME type and preserves its true file extension. It streams PCM microphone audio over WebSocket for live transcription and preserves the completed recording for playback and download; uploaded audio uses the batch endpoint. It never uses the browser Web Speech API.

## Verification

```bash
# frontend/
npm run lint
npx tsc --noEmit

# backend/ (activated virtual environment)
pytest
```

Current automated verification: 39 backend tests, live Neon PostgreSQL CRUD/persistence verification, frontend ESLint, TypeScript validation, and the Webpack production build pass. Browser microphone verification still depends on browser permission and a real microphone.

## Current boundary

Automatic English/Hindi recognition, Hindi-English mixed recognition, live partial/final transcription, upload validation, timestamped segments, repetition checks, recording playback/download, PostgreSQL transcription CRUD, and the local History dashboard are implemented. Recognition quality still depends on real audio, accents, microphone quality, and the configured model; short Hindi clips may be confused with Urdu acoustically and require representative audio validation. Ownership isolation, cloud deployment, and optional text translation remain upcoming work.
