# Wakilz Rasen Backend

FastAPI backend that bridges Wakilz's WebRTC voice calls into [Rasen.ai](https://rasen.ai) as the conversation runtime, then routes call results to Firestore and HubSpot.

## Architecture

```
Browser (WebRTC) → WakilzVoiceBackend → Rasen.ai WS (PCM16 bridge)
                                      ← Webhook → Firestore + HubSpot
```

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/session` | Issue short-lived JWT to browser |
| POST | `/start` | Create Rasen agent session |
| POST | `/sessions/{id}/api/offer` | WebRTC SDP exchange + start audio bridge |
| POST | `/webhooks/rasen` | Rasen call.completed / call.analyzed |
| GET | `/api/client/verify?key=wklz_…` | Client key → scoped JWT |
| GET | `/api/conversations` | List conversations (admin/client scoped) |
| GET | `/api/conversations/{id}` | Single conversation detail |
| GET | `/api/conversations/{id}/audio` | Fresh recording URL |
| GET | `/health` | Uptime + active sessions |

## Local Development

> [!IMPORTANT]
> **Requires Python 3.11 or 3.12.** Python 3.13+ not yet supported (`av` and `pydantic-core` lack pre-built wheels).
> Use `py -3.12 -m venv .venv` on Windows if 3.14 is your default.

```bash
# 1. Create venv and install deps
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Mac/Linux

pip install -r requirements.txt

# 2. Copy env file
copy .env.example .env
# Edit .env with your values

# 3. Run
python -m server.core.main
# Server starts at http://localhost:8080
```

## Environment Variables

See [`.env.example`](.env.example) for all variables.

Required:
- `RASEN_API_KEY` — Workspace key from Rasen dashboard
- `RASEN_AGENT_ID` — Published agent ID
- `HUBSPOT_ACCESS_TOKEN` — HubSpot private app token
- `FIREBASE_PROJECT_ID` — Firebase project (`wakilz-dasboard`)
- `JWT_SECRET` — Random 32-char hex

Optional (add later):
- `RASEN_WEBHOOK_SECRET` — From Rasen dashboard → Developers → Webhooks
- `ADMIN_API_KEY` — Simple admin key for dashboard calls

## Cloud Run Deployment

```bash
# Build and deploy to GCP Cloud Run (asia-south1)
gcloud run deploy wakilz-voice \
  --source . \
  --region asia-south1 \
  --port 8080 \
  --min-instances 1 \
  --allow-unauthenticated
```

Then set env vars in Cloud Run console and update `VITE_API_BASE_URL` in the frontend `.env`.

## Firestore Collections

- `/conversations/{callId}` — call records (clientId scoped)
- `/client_keys/{key}` — client key → clientId mapping
- `/users/{uid}` — Firebase Auth users (admin role)

## Adding a New Client

In Firebase Console → Firestore → `client_keys` → Add document:
```
Document ID: wklz_<random>   ← this is their secret key
clientId:    their_slug
displayName: "Their Company"
active:      true
```

Generate key: `python -c "import secrets; print('wklz_' + secrets.token_urlsafe(12))"`
