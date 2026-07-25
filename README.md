# Patient Registration Voice AI Agent

A voice AI agent that registers new patients over the phone and exposes the
same data through a REST API. Built for the CareCloud technical assessment.

**Live demo:**
- Phone number: Not available — Vapi's free number provisioning was disabled
  for this organization, and importing a paid number via Twilio wasn't
  feasible within the time/payment constraints of this assessment. As a
  working alternative, the voice agent is reachable live, at any time, via
  browser at the `/demo` link below — no phone call required.
- Voice agent demo (browser): https://patientvoiceagentforcarecloud-production.up.railway.app/demo
- API base URL: https://patientvoiceagentforcarecloud-production.up.railway.app

## Architecture

```
Caller --(phone)--> Vapi (telephony + STT + TTS + LLM)
                        |
                        | POST /vapi/tool-call  (function/tool calls)
                        v
                  FastAPI service  <-----> SQLite (patients.db)
                        ^
                        | REST API (GET/POST/PUT/DELETE /patients)
                        |
              External clients / reviewers
```

The voice agent and the REST API share the same service layer
(`database.py`), so there is one source of truth for persistence and
validation logic — the voice agent doesn't duplicate business rules, it just
calls the same functions the REST API calls.

**Files:**
- `main.py` — FastAPI app: REST endpoints + `/vapi/tool-call` webhook
- `database.py` — SQLite schema and CRUD functions
- `validation.py` — Pydantic models enforcing the data model server-side,
  independent of whatever the voice agent already validated
- `system_prompt.md` — the LLM system prompt for the Vapi assistant
- `vapi_tool_definitions.json` — tool/function schemas to paste into Vapi

## Tech stack & why

| Layer | Choice | Why |
|---|---|---|
| Telephony/STT/TTS/LLM orchestration | Vapi | Abstracts the hardest parts (call handling, speech, LLM turn management) so the 3-hour budget goes into business logic and prompt quality, not plumbing |
| Backend | FastAPI | Async, built-in request validation, fast to write, matches my existing experience |
| Database | SQLite | Zero setup, file-based, persists to disk — meets the "survives restart" requirement without provisioning a managed Postgres instance under time pressure. Documented trade-off below. |
| Validation | Pydantic | Declarative, catches bad data before it hits the DB, reused for both REST and voice paths |
| Hosting | Railway | Git-push deploy, gives a public HTTPS URL Vapi can call, no manual server config |

## Setup

```bash
pip install -r requirements.txt --break-system-packages
uvicorn main:app --host 0.0.0.0 --port 8000
```

Runs at `http://localhost:8000`. SQLite file `patients.db` is created
automatically on first run, with one seed patient (Jane Doe) for demo
purposes.

### Environment variables
None required for the backend itself — it has no secrets (no API keys are
called from this service; the LLM and telephony calls happen inside Vapi,
configured separately in their dashboard with their own key management).
If deploying and Vapi is configured to hit a non-default port, set `PORT`
(Railway sets this automatically).

### Deploying
1. Push this repo to GitHub.
2. Railway → New Project → Deploy from GitHub repo. Railway auto-detects the
   `Procfile`.
3. Copy the resulting public URL.
4. In Vapi: create an Assistant, paste `system_prompt.md` as the system
   prompt, attach the four tools from `vapi_tool_definitions.json` (replace
   `YOUR-RAILWAY-URL` with the real Railway URL first), pick an LLM and a
   voice, provision a phone number.

## API reference

All responses use the envelope `{ "data": ..., "error": ... }`.

| Method | Endpoint | Notes |
|---|---|---|
| GET | `/patients` | Optional filters: `?last_name=`, `?date_of_birth=`, `?phone_number=` |
| GET | `/patients/{id}` | 404 if not found or soft-deleted |
| POST | `/patients` | 201 on success, 422 with field-level errors on invalid input |
| PUT | `/patients/{id}` | Partial update, 404 if not found |
| DELETE | `/patients/{id}` | Soft delete (sets `deleted_at`), 404 if not found |

## Voice agent design

The prompt (`system_prompt.md`) drives a conversational flow: greet →
check for existing patient by phone → collect required fields → offer
optional fields → **read back everything and require explicit
confirmation** → save → confirm outcome to caller. Field-level validation
errors from the backend are surfaced back to the LLM as plain-English
messages naming the specific bad field, so the agent re-prompts only that
field instead of restarting the whole call.

Duplicate detection: `check_existing_patient` is called as soon as a phone
number is captured. If a match exists, the agent offers to update instead
of creating a duplicate record.

## Known limitations & trade-offs

- **No phone number provisioned.** Vapi disabled free number provisioning
  for this organization, and I don't have a way to pay for a Twilio number
  within this assessment's constraints. Documented per the assessment's own
  FAQ guidance for this exact scenario. In its place, `/demo` embeds Vapi's
  web voice widget so the assistant is reachable live in-browser, anytime,
  without needing me present — same LLM, same tools, same database, just a
  different transport than a PSTN phone call.
- **SQLite, not Postgres.** Fine for a single-instance demo; would move to
  Postgres for concurrent writes and multi-instance deployment in
  production.
- **No auth on the REST API.** Acceptable for this assessment per the "no
  HIPAA compliance needed" note; a real system would need auth (e.g. API
  keys or OAuth) before any patient data touched it.
- **No automated test suite** — validated manually via curl during
  development (see commit history / dev notes). Given more time this would
  be the first addition.
- **No call transcript storage** — logs the final collected data payload to
  stdout per the observability requirement, but doesn't persist full
  transcripts. Bonus feature, not implemented due to time.
- **No multi-language support implemented** (bonus feature, not attempted).
- **Dropped call handling**: relies on Vapi's built-in reconnection
  behavior; no custom mid-call state recovery was built server-side beyond
  keeping each tool call idempotent-ish (re-registering with the same phone
  number is caught by duplicate detection rather than silently duplicating).

## Next steps (if given more time)
- Automated tests (pytest) for the API layer.
- Migrate to Postgres with a proper migration tool (Alembic).
- Add basic API-key auth.
- Persist call transcripts linked to patient_id.
- Duplicate-detection bonus is implemented; would add appointment
  scheduling and a simple read-only dashboard next.
