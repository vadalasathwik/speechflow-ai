# SpeechFlow AI

Production-oriented MVP groundwork for real-time Hindi-English code-switched speech transcription, built for the Procucev Enterprise Solutions technical hiring assignment.

Phase 1 establishes the monorepo foundation only: frontend and backend services, configuration, PostgreSQL Compose, SQLAlchemy/Alembic plumbing, and a tested health endpoint. Streaming, speech recognition, and transcript management are deliberately deferred.

## Architecture

```text
frontend/  Next.js App Router + TypeScript + Tailwind CSS
     | HTTP/WebSocket (future phases)
backend/   FastAPI + Pydantic + SQLAlchemy 2.0 + Alembic
     |
PostgreSQL Docker Compose service
```

## Prerequisites

- Node.js 20.9+
- Python 3.11+
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
python3.11 -m venv .venv
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

## Environment variables

| File | Purpose |
| --- | --- |
| `.env` | Docker Compose PostgreSQL defaults |
| `backend/.env` | API settings, CORS origins, database URL |
| `frontend/.env.local` | Browser-visible backend base URL |

`ALLOWED_ORIGINS` is a JSON list, e.g. `ALLOWED_ORIGINS=["http://localhost:3000"]`.

## Verification

```bash
# frontend/
npm run lint
npx tsc --noEmit

# backend/ (activated virtual environment)
pytest
```

## Phase 1 boundary

No speech recognition, Faster-Whisper downloads, recording, WebSockets, transcript models, or transcript CRUD are included.
