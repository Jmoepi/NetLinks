# NetLinks prototype

NetLinks turns SME documents and a buyer's RFQ into a structured, evidenced, explainable shortlist. Eligibility rules run as plain code, AI helps with document understanding and semantic matching, and a human makes every decision. Every step is recorded in an append-only audit log.

This repo is the hackathon demo build for the managed-IT scenario in [`docs/demo-script.md`](docs/demo-script.md).

> **Warning: no real authentication. Do not expose this publicly.**
> The sign-in page and the "Switch account (demo)" menu are a simulation: anyone who can reach the app can act as any SME, the buyer or YES Admin. Role permissions are enforced server-side, but identity is not checked. All ports in `docker-compose.yml` bind to `127.0.0.1` only. Keep it that way, and don't run this on a shared network host, behind a tunnel or on a public cloud instance. Production would use Amazon Cognito.

> **All data is fictional.** Companies, people, clients, certificates, insurance schedules and tax letters are invented for the demo. Every PDF is watermarked "FICTIONAL - DEMO ONLY" and has no real logos or seals. Every screen shows a "Fictional demo data" banner.

## Run it

Requirements: Docker with Compose v2. No AWS account is needed for the default Cached AI mode.

```bash
docker compose up -d --build
```

| URL | What |
|---|---|
| http://localhost:3000 | Web app (Next.js) |
| http://localhost:8000/api/health | API health check, returns `{"status":"ok"}` |
| http://localhost:8000/docs | API docs (FastAPI) |

On first start the backend creates the schema and seeds the demo data through the real ingestion pipeline, using the committed AI cache. To start again from a clean database:

```bash
docker compose down -v
docker compose up -d --build
```

Between rehearsals, use **YES Admin -> Reset demo** instead. It restores the seed state and sets AI mode back to Cached.

Environment variables are documented in [`.env.example`](.env.example). `docker-compose.yml` already has working local defaults. Copy it to `.env` only to override them, and never commit `.env` (it is gitignored).

## Landing page, sign-in and pagination

- `/` is a public landing page: what NetLinks does, how it works, who it is for, trust and privacy, roadmap, and a **Sign in to the demo** link.
- `/login` is a simulated sign-in. Pick a role (SME, Buyer or YES Admin), then a persona, then **Sign in**. The demo emails are:

  | Persona | Demo email |
  |---|---|
  | SME: Thuto Tech Solutions | `thuto@demo.netlinks.local` |
  | SME: Mmapula Digital Workplace | `mmapula@demo.netlinks.local` |
  | SME: Zola Systems | `zola@demo.netlinks.local` |
  | SME: Bright Path Networks | `brightpath@demo.netlinks.local` |
  | SME: Lerato Web Studio | `lerato@demo.netlinks.local` |
  | Buyer: Naledi (Ubuntu Office Parks) | `naledi@demo.netlinks.local` |
  | YES Admin | `admin@demo.netlinks.local` |

  The password field shows `demo`. It is never checked, sent or stored.
- Visiting a workspace page while signed out goes to `/login?next=…`, and signing in returns you there. Pages that belong to another role show "Access denied for this role" with a **Switch account** link.
- The account menu in the top bar shows the current persona and role. **Switch account (demo)** switches persona in one click; **Sign out** returns to `/`.
- Pagination: the audit log shows 20 entries per page, newest first, with **Event type** and **Role** filters. Other long lists show 10 per page. The controls are hidden when everything fits on one page, and the page is kept in the URL (`?page=2`, `?eligible_page=2`, …), so refresh and Back work.
- API: `GET /api/audit?page=&page_size=&action=&actor_role=` and `GET /api/opportunities?page=&page_size=`. Without these parameters both endpoints return their previous, unpaginated shapes.

## Demo walkthrough

Sign in at `/login` and switch with **Switch account (demo)** in the top bar. The times match section 2 of the demo script. Start from a fresh Reset demo with AI mode Cached.

| Script time | Account | What to do in the app |
|---|---|---|
| 0:00-0:40 | any | Problem statement (talk only). |
| 0:40-1:15 | none -> SME: Thuto Tech Solutions | Open the landing page, click **Sign in to the demo**, sign in as Thuto. Point at **Switch account (demo)** and the "AI mode: Cached" badge. |
| 1:15-3:15 | SME: Thuto Tech Solutions | **My profile**: upload `demo-assets/Thuto_Capability_Statement.pdf`, `Thuto_Technician_Certifications.pdf` and `Thuto_InfoSec_POPIA_Policy.pdf` together. Show the `AI-extracted` badges and **View source**. Confirm the low-confidence PI cover as R2,000,000. Edit technician count 9 -> 11 with a note (badge becomes `SME-confirmed`). Accept the consent prompt. |
| 3:15-4:30 | Buyer - Naledi (Ubuntu Office Parks) | **Opportunities** -> the managed IT opportunity. Click **Structure requirements** (cached result, PI minimum R1,000,000). Raise the PI minimum to R2,000,000, show the 40/25/20/15 weights, then **Save**. |
| 4:30-6:45 | Buyer | Open the results page and click **Run matching**. You should see Eligible (2): Thuto #1, Mmapula #2 · Needs Review (2): Zola (PI expires 10 days before closing), Bright Path (technician count 15 vs 4) · Not Eligible (1): Lerato (no Gauteng region). |
| 6:45-7:45 | Buyer | **Shortlist** Thuto and Mmapula. **Request information** from Zola (status becomes Awaiting SME). **Request clarification** from Bright Path. Move Mmapula to the top of the shortlist with a written reason. Open **Audit log**. |
| 7:45-8:30 | SME: Zola Systems, then SME: Lerato Web Studio | Zola **Readiness**: see the request and action, then upload `demo-assets/Zola_PI_Insurance_Schedule_Renewed.pdf`. Switch account (demo) to Buyer and **Re-run matching**: Zola is now Eligible. Switch account (demo) to Lerato **Readiness** to show the Gauteng requirement. |
| 8:30-9:15 | YES Admin | **YES dashboard**: pipeline before and after, readiness gaps, requested skills, overrides with reasons, fairness by province and size. |
| 9:15-10:00 | any | Architecture slide and close (talk only). |

On the results page, each card shows its capability-match explanation directly (Mmapula's reads "AI-assisted semantic match"); the full Score breakdown stays in its collapsible panel.
### Reset the demo
YES Admin -> **Reset demo** -> "Yes, reset the demo". This restores the seed state (Thuto with no documents and consent pending, no match runs, requests or decisions) and sets AI mode back to Cached. The reset itself is recorded in the audit log. API equivalent: `POST /api/admin/reset` with `X-Demo-Role: admin`. Reset before every rehearsal and before going on stage.
Fallbacks (script section 3):
- **Live AI**: YES Admin -> AI mode -> Live. This only works if Bedrock is configured (see below). Otherwise the option is disabled and shows the reason. To prove the pipeline is real, Reset demo, switch to Live, then upload Thuto's PDF as SME: Thuto.
- **No Wi-Fi**: everything runs locally. Cached mode makes no network calls.
- **Broken state**: YES Admin -> **Reset demo**.

Rehearse the Live toggle and at least one real browser file-picker upload before demo day. Neither has been exercised in this environment.

## AI modes and the cache

- **Cached** (default): AI results are read from `ai-cache/` (extraction per PDF, RFQ structuring, embeddings). Each file records `provider`, `model_id`, `generated_by`, `generated_at` and `prompt_version`. The UI and the audit log show these values as stored.
- **Live**: calls Amazon Bedrock (Claude via `converse` for extraction and RFQ structuring, Titan Text Embeddings v2 for embeddings). Live results are recorded in the database but never written back to `ai-cache/`.

**The committed cache is local-fallback, not Bedrock.** No AWS credentials were available when it was built, so it came from a rule-based parser (`local-rules-v1`) and a concept-lexicon embedding (`local-lexicon-v1`). Every record is labelled `local-fallback (regenerate with Bedrock before demo)`, and the app never calls it Bedrock. This includes Mmapula's "AI-assisted semantic match": with the committed cache, that score comes from the local lexicon. Regenerate the cache with Bedrock before the demo so that the script's line "generated by our pipeline from these exact documents" holds.

### Regenerate the cache with Bedrock

1. Set these variables in your shell or in `.env`. `docker-compose.yml` passes them through to the backend.

   | Variable | Value |
   |---|---|
   | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN` | Credentials with Bedrock `InvokeModel`/`Converse` access (or set `AWS_PROFILE` and make the profile available in the container) |
   | `BEDROCK_REGION` | Default `af-south-1`. Confirm model availability there first. |
   | `BEDROCK_EXTRACTION_MODEL_ID` | A Claude model ID or cross-Region inference profile ID your account can use (no default) |
   | `BEDROCK_EMBEDDING_MODEL_ID` | Default `amazon.titan-embed-text-v2:0` |

2. Regenerate. This replaces every file in `ai-cache/`, so the cache always reflects exactly one provider:

   ```bash
   docker compose run --rm backend python -m app.cli regenerate-cache --provider bedrock
   ```

   Example with inline variables:

   ```bash
   docker compose run --rm \
     -e AWS_ACCESS_KEY_ID=... -e AWS_SECRET_ACCESS_KEY=... -e AWS_SESSION_TOKEN=... \
     -e BEDROCK_EXTRACTION_MODEL_ID=... \
     backend python -m app.cli regenerate-cache --provider bedrock
   ```

   The command exits with an error if credentials or model IDs are missing.

3. Re-run the tests (see below). The rankings are designed to hold under the Titan calibration, but Bedrock's extraction and scores must be checked. Then **Reset demo** (or `docker compose down -v && docker compose up -d --build`) so the seed data is re-ingested from the new cache. Walk through the demo once and check the expected outcomes.

4. Commit the new `ai-cache/` files.

To rebuild the local-fallback cache instead, use `--provider local-fallback`.

### Regenerating the demo documents

The PDFs in `demo-assets/` are generated deterministically, and cache keys are the SHA-256 of each file's bytes. **If you change or regenerate the documents, you must regenerate the cache too**, or uploads and seeding will hit "No cached AI result" in Cached mode.

```bash
docker compose run --rm backend python tools/generate_demo_docs.py --out /demo-assets
docker compose run --rm backend python -m app.cli regenerate-cache --provider bedrock   # or local-fallback
```

## Tests

```bash
docker compose run --rm backend pytest -q        # unit + integration tests (uses the netlinks_test database)
docker compose run --rm backend ruff check .     # backend lint
cd frontend && npm ci && npm run lint && npm run typecheck && npm run build
```

The integration tests drive the full demo flow through the API and assert the outcomes listed above, plus RBAC and audit behaviour.

## Architecture
```text
Next.js PWA (frontend, :3000)
   │  REST + X-Demo-Role headers (simulated sign-in)
   ▼
FastAPI (backend, :8000)
   ├─ deterministic eligibility rules + fit scoring (plain code, no LLM)
   ├─ AI gateway: Cached (ai-cache/) or Live (Amazon Bedrock: Claude for extraction/RFQ structuring,
   │  Titan Text Embeddings v2 for semantic matching)
   ├─ document storage: local volume, or private encrypted S3 (STORAGE_BACKEND=s3)
   └─ PostgreSQL 16 + pgvector (profiles, field lineage, embeddings, match runs, append-only audit log)
```
Locally all three services run in Docker Compose. The production target is described below.
## Layout

- `backend/`: FastAPI app. `app/engine/` holds the deterministic eligibility rules and fit scoring (no LLM). `app/ai/` is the AI gateway with Bedrock and local-fallback providers. `app/ingestion/` handles PDF text and field lineage. `app/services/` handles matching, seed and dashboard.
- `frontend/`: Next.js (app router, TypeScript) web UI. UI design tokens and patterns: `docs/design-system.md` (icons via lucide-react, no remote assets).
- `demo-assets/`: fictional demo PDFs and the raw RFQ text.
- `ai-cache/`: committed AI results used in Cached mode.
- `db/init/`: creates the test database.
- `docs/demo-script.md`: the demo script and acceptance criteria.

## Production target (not deployed)

The target is AWS `af-south-1` (Cape Town): ECS Fargate for the backend and frontend, RDS PostgreSQL with pgvector, a private encrypted S3 bucket for documents (`STORAGE_BACKEND=s3`, `S3_BUCKET`), Amazon Bedrock for extraction and embeddings, and Amazon Cognito for authentication. This repo only documents the configuration in `.env.example`. It has no infrastructure code or deploy scripts, and nothing has been deployed. Confirm the Bedrock inference region and POPIA position before any live pilot.

## Out of scope (roadmap)

- Funding and grant matching
- Structured buyer feedback with an SME right of reply
- Procurement portal integrations
- OCR for scanned documents (the prototype reads text-based PDFs only)
- Real authentication with Amazon Cognito (replacing the simulated sign-in)
- AWS deployment (infrastructure as code, CI/CD)
- Verification of certifications against vendor records (the prototype separates SME-confirmed from verified)
