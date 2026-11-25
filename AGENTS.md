# SpeechFlow AI contribution guide

## Architecture

- `frontend/` is a Next.js App Router application. Keep browser-facing UI and client state here.
- `backend/` is a FastAPI service. Route modules stay thin; move domain logic into feature-specific service modules as features are added.
- PostgreSQL is the system of record. SQLAlchemy models inherit from `app.db.base.Base`; schema changes require Alembic migrations.
- Real-time audio, Faster-Whisper integration, WebSockets, transcript CRUD, and authentication are intentionally out of scope for Phase 1.

## Standards

- Use TypeScript with strict types and the `@/` alias in the frontend.
- Use Python type hints and Pydantic models for API contracts.
- Read configuration from environment variables only. Update the appropriate `.env.example`; never commit secrets.
- Keep API paths under `API_V1_PREFIX` (currently `/api`).
- Add a test for each externally visible backend behavior.

## Development rules

- Do not add paid APIs, RAG frameworks, LangChain, vector databases, or unrequested authentication.
- Run frontend lint and TypeScript validation plus backend tests before handoff.
- Generate migrations with `alembic revision --autogenerate -m "description"`, then inspect them.
- Preserve Apple Silicon compatibility: use platform-neutral images and avoid x86-only assumptions.
