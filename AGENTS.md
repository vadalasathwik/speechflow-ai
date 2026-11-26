# SpeechFlow AI contribution guide

## Architecture

- `frontend/` is a Next.js App Router application. Keep browser-facing UI and client state here.
- `backend/` is a FastAPI service. Route modules stay thin; move domain logic into feature-specific service modules as features are added.
- PostgreSQL is the system of record. SQLAlchemy models inherit from `app.db.base.Base`; schema changes require Alembic migrations.
- `app.services.transcription` owns batch Faster-Whisper inference. Keep provider-specific code behind this service boundary.
- Browser recording is owned by `frontend/src/hooks/use-audio-recorder.ts`; it must release media tracks, timers, audio contexts, and object URLs on every end path.
- WebSockets, microphone streaming, transcript CRUD, and authentication remain out of scope.

## Standards

- Use TypeScript with strict types and the `@/` alias in the frontend.
- Use Python type hints and Pydantic models for API contracts.
- Read configuration from environment variables only. Update the appropriate `.env.example`; never commit secrets.
- Keep API paths under `API_V1_PREFIX` (currently `/api`).
- Add a test for each externally visible backend behavior.
- Tests must mock the transcription service; do not download models during the automated suite.
- Uploaded audio is temporary and must always be deleted in a `finally` path.

## Development rules

- Do not add paid APIs, RAG frameworks, LangChain, vector databases, or unrequested authentication.
- Run frontend lint and TypeScript validation plus backend tests before handoff.
- Generate migrations with `alembic revision --autogenerate -m "description"`, then inspect them.
- Preserve Apple Silicon compatibility: use platform-neutral images and avoid x86-only assumptions.
- Preserve actual browser MIME types and extensions; never relabel recorded containers.
