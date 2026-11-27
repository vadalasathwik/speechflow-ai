# Free temporary recruiter demo

This is a temporary public demonstration from the development Mac, not a cloud deployment. It costs nothing and does not require a Cloudflare account, domain, payment method, subscription, or new speech model. The Mac performs Faster-Whisper inference and remains the service host.

## Design

`cloudflared` exposes only Caddy on `127.0.0.1:8080`. Caddy sends `/api/*` and `/ws/*` to FastAPI on `127.0.0.1:8000`, and every other path to Next.js on `127.0.0.1:3000`. The browser therefore uses one `https://*.trycloudflare.com` origin:

```
browser (HTTPS / WSS) -> Cloudflare Quick Tunnel -> Caddy :8080
                                                   |-> Next.js :3000
                                                   |-> FastAPI :8000 -> Neon PostgreSQL
```

The frontend leaves `NEXT_PUBLIC_API_BASE_URL` empty for this mode, so its REST calls use `/api` and its WebSocket uses the current page origin at `/ws/transcribe`. The anonymous-session cookie is first-party, HttpOnly, Secure (because the API is run with `ENVIRONMENT=production`), and `SameSite=Lax`. FastAPI still applies the existing exact Origin and CSRF-token checks. There is no wildcard CORS or authorization bypass.

## Prerequisites (one time)

Install only the networking tools; this does not install or download any speech model:

```bash
brew install cloudflared caddy
cloudflared --version
caddy version
```

Use the existing project dependencies and existing `backend/.env` containing the Neon URL. Do not copy it into the repository or share it. Ensure the existing local Large-v3 Turbo cache is reachable by the backend process. Keep the Mac on AC power, awake, and on a stable unrestricted network.

## Start the demo

Open four terminals at the repository root. The order below lets the temporary hostname be known before FastAPI begins enforcing its exact Origin.

### 1. Start Next.js in production mode with same-origin API paths

Use a production Next.js server for the recruiter demo. `next dev` opens development hot-reload WebSockets that are unrelated to `/ws/transcribe` and make browser Network panels noisy.

```bash
cd frontend
NEXT_PUBLIC_API_BASE_URL= npm run build -- --webpack
NEXT_PUBLIC_API_BASE_URL= npm run start -- --hostname 127.0.0.1 --port 3000
```

### 2. Start Caddy, bound locally only

```bash
cd /Users/sathwik/Developer/speechflow-ai
caddy run --config demo/Caddyfile --adapter caddyfile
```

### 3. Start the Quick Tunnel and copy its printed URL

```bash
cloudflared tunnel --url http://127.0.0.1:8080
```

Cloudflare prints a URL such as `https://words.trycloudflare.com`. Keep this process running. If `~/.cloudflared/config.yaml` exists, Quick Tunnel may refuse to start; temporarily rename that local configuration and restore it afterward. Do not put a Quick Tunnel configuration file in this repository.

### 4. Start FastAPI with the exact generated Origin

Replace the value only in your terminal; do not put the changing hostname in tracked files. The existing `.env` supplies `DATABASE_URL`; the command below supplies production-only values.

```bash
cd /Users/sathwik/Developer/speechflow-ai/backend
export DEMO_ORIGIN='https://words.trycloudflare.com'
export SESSION_TOKEN_PEPPER="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
ENVIRONMENT=production \
DEBUG=false \
ALLOWED_ORIGINS="[\"$DEMO_ORIGIN\"]" \
SESSION_COOKIE_SAMESITE=lax \
WHISPER_MODEL=large-v3-turbo \
WHISPER_DEVICE=cpu \
WHISPER_COMPUTE_TYPE=int8 \
WHISPER_WARMUP_ON_START=true \
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1 --proxy-headers
```

`WHISPER_WARMUP_ON_START=true` loads the already-approved model once during controlled backend startup. It must not be set if the named model is unavailable locally, because Faster-Whisper may otherwise attempt a network fetch. The single worker avoids duplicating the approximately 1,939 MiB local model RSS. Do not run multiple inference workers.

### Local Caddy smoke test

If testing through `http://localhost:8080` before starting the public tunnel, FastAPI must allow that exact browser origin. For the local-only backend process, use `ALLOWED_ORIGINS=["http://localhost:8080"]` (or include both `:3000` and `:8080` when testing direct Next.js as well). Do not use `*`. A browser opened at local Caddy constructs `ws://localhost:8080/ws/transcribe`; a public Quick Tunnel page constructs `wss://<generated-host>/ws/transcribe` and must instead use the exact `DEMO_ORIGIN` configuration above.

Open the exact `DEMO_ORIGIN` in the browser and share that URL with the recruiter. A tunnel URL changes whenever the `cloudflared` process ends; each new URL requires updating `DEMO_ORIGIN` and restarting FastAPI before the demo is usable. The currently issued browser session expires after the configured 30 days, but a new Quick Tunnel hostname is normally much shorter-lived.

For a more private review, current Cloudflare Quick Tunnel documentation supports adding `--allowed-mail recruiter@example.com` to the `cloudflared` command. Confirm the installed `cloudflared` version supports it before relying on that option.

## Verification checklist

Use the public HTTPS URL (not localhost) and check:

1. The page loads over HTTPS and `GET /api/health` returns 200 through the same URL.
2. Browser devtools shows a Secure, HttpOnly `speechflow_session` cookie after opening History; no cookie is sent to a separate API domain.
3. Microphone permission works and the browser opens `wss://<temporary-host>/ws/transcribe`.
4. English, Hindi, and Hindi-English speech produces the actual model output without translation.
5. Upload, playback, download, Save, History search, view, edit, and delete work.
6. Refresh retains the same visitor's history; a private/incognito browser session cannot list, read, edit, or delete the first session's records.
7. Network responses, browser assets, terminal output, and Git status contain no `DATABASE_URL`, session pepper, model weights, or audio recording.

If Caddy returns `502`, FastAPI is not listening on `127.0.0.1:8000`; restart it before retrying. If the WebSocket handshake returns `403` or closes with code `1008`, the browser Origin is not in `ALLOWED_ORIGINS`: use `http://localhost:8080` for a local Caddy page or the exact `DEMO_ORIGIN` for the Quick Tunnel, then restart FastAPI. If the model starts downloading, stop the backend; correct the existing model path/cache before retrying.

## Stop and revoke access

Press `Ctrl+C` in the cloudflared terminal first. The public URL immediately stops routing. Then stop Caddy, Next.js, and FastAPI with `Ctrl+C`. Clear `DEMO_ORIGIN` and `SESSION_TOKEN_PEPPER` from that terminal if desired:

```bash
unset DEMO_ORIGIN SESSION_TOKEN_PEPPER
```

## Limits and security boundary

Cloudflare documents Quick Tunnels as temporary development/test URLs with no uptime guarantee, changing hostnames, a 200 in-flight request limit, and no SSE support. This app uses WebSockets, not SSE, but WebSocket behavior must still be tested on the live URL before sharing it. Anyone holding an unprotected tunnel URL can reach the demo; anonymous sessions isolate transcription records but are not user accounts. Do not use this setup for persistent public hosting, sensitive recordings, or the assignment's permanent cloud-hosted deliverable. The Mac must stay awake and connected, and its CPU/RAM/network determine capacity and latency.
