# Diamond Intel

Diamond Intel is an MLB-wide AI baseball analysis app focused on transforming postgame outcomes into structured team-level insights that can power future AI experiences.

Current milestone: establish a backend foundation that stores structured postgame baseball insight reports in PostgreSQL before any LLM integration.

## Current structure

```text
backend/
  app/
    db.py
    models.py
    schemas.py
    report_service.py  ← report persistence + generation (reuse/regenerate policy)
    main.py   ← seed / sample generation entrypoint
    api.py    ← FastAPI routes
  examples/
    generate-sample-report-request.json
    post-report-request.json          ← canonical POST /reports example (single source of truth)
    postgame-report-contract.json
  tests/
    test_reports_api.py
  sql/
    generated_reports_queries.sql  ← local dev helper queries
  requirements.txt
sql/
  schema.sql
README.md
```

## Local setup

1. Create a PostgreSQL database named `baseball_analyst`.
2. Apply the schema:
   ```bash
   psql baseball_analyst < sql/schema.sql
   ```
3. Install dependencies:
   ```bash
   pip install -r backend/requirements.txt
   ```
4. Set `DATABASE_URL` if needed (default: `******localhost:5432/baseball_analyst`).

## Seed / idempotency test

Run the seed script as many times as you like — it upserts on `(game_id, team_id, persona_key, report_type)`:

```bash
cd backend && python -m app.main
```

On the **first run** the output shows `Inserted`; every subsequent run shows `Updated`:

```
Inserted report id: 5
  Identity: game_id=1, team_id=1, persona_key='team_analyst', report_type='postgame_insight'
  Headline : 'Guardians postgame snapshot'
  Confidence: medium
  Result   : loss
```

### Verifying update behavior manually

1. Open `backend/app/main.py` and change the `headline` variable or update `DEFAULT_SAMPLE_REPORT` in `backend/app/report_service.py` (for example, change `"confidence"` to `"high"`).
2. Re-run the script — the output will say `Updated report id: <same id>` and reflect the new value.
3. Use query 4 in `backend/sql/generated_reports_queries.sql` to confirm in the database: the `row_age` column will be nonzero, confirming the row was not recreated.
4. To start fresh (test a clean insert), run query 5 from that file to delete the seed row, then re-run the script.

## Local tests

Run the backend tests from `backend/`:

```bash
cd backend && python -m unittest discover -s tests -v
```

The test suite uses FastAPI's `TestClient` plus an in-memory SQLite database, so no local PostgreSQL instance is required for automated validation.
`backend/requirements.txt` includes the `httpx` dependency required by FastAPI's test client.

The suite currently covers:

- `POST /reports` — contract validation, blank-field rejection, mismatch checks, upsert behaviour
- `POST /reports/generate` — insert, reuse, force-regenerate, unsupported type rejection
- `GET /reports/latest` — most-recent return, team filter, 404 on no match
- `GET /reports/by-identity` — happy path and 404
- `GET /reports` — list/filter
- Canonical example contract: `test_canonical_post_example_validates_against_request_model`

## Canonical example and anti-drift safeguard

`backend/examples/post-report-request.json` is the **single canonical source** for the `POST /reports` request body.

- The Swagger UI example in `/docs` is loaded directly from this file at startup (`api.py` reads it with `json.loads`).
- The `test_canonical_post_example_validates_against_request_model` test parses the file and validates it against the `ReportUpsertRequest` Pydantic model in CI.
- Any schema change that breaks the file's shape will fail CI immediately rather than silently drifting.

To exercise the canonical example directly:

```bash
curl -s -X POST http://localhost:8000/reports \
  -H "Content-Type: application/json" \
  -d @backend/examples/post-report-request.json | python -m json.tool
```

## Report identity and regeneration policy

A report is uniquely identified by the four-field identity tuple:

```
(game_id, team_id, persona_key, report_type)
```

One row per identity is enforced by a database unique constraint.

| Endpoint | Behaviour |
|----------|-----------|
| `POST /reports` | Always upserts (insert → `"inserted"`, overwrite → `"updated"`) |
| `POST /reports/generate` (default) | Returns the stored row unchanged → `"reused"` |
| `POST /reports/generate` + `"force": true` | Rebuilds from local data and overwrites → `"regenerated"` (or `"inserted"` if no row existed) |
| `POST /reports/generate-sample` | Always upserts using the deterministic sample data |

Automatic regeneration does not happen — a report is only rebuilt when you explicitly call the generate endpoint with `"force": true` or submit a new payload via `POST /reports`.

## API

Start the development server:

```bash
cd backend && python -m uvicorn app.api:app --reload
```

### VS Code on Windows quick start

In a VS Code terminal (PowerShell):

```powershell
cd backend
py -m uvicorn app.api:app --reload
```

Keep that terminal running, then use a second VS Code terminal for `curl` examples.

Interactive docs: <http://localhost:8000/docs>

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/reports` | Create or update a report (upsert); requires a top-level `report` wrapper |
| `POST` | `/reports/generate` | Generate and persist a report from local data, honouring the reuse/regenerate policy |
| `POST` | `/reports/generate-sample` | Generate and persist the deterministic local sample report from identity metadata |
| `GET`  | `/reports/latest` | Return the single most-recently created report; filter with `?game_id=&team_id=&persona_key=&report_type=` |
| `GET`  | `/reports/by-identity` | Fetch a report by logical identity tuple |
| `GET`  | `/reports/{id}` | Fetch a report by primary-key id |
| `GET`  | `/reports` | List reports (newest first); filter with `?game_id=&team_id=&persona_key=&report_type=` and paginate with `?limit=&offset=` |

#### `POST /reports` body shape (important)

- Send the **full wrapped request body** to `POST /reports`:
  - `{ "report": { ...identity/persistence fields..., "insight_json": { ... } } }`
- `backend/examples/postgame-report-contract.json` contains only the **inner** `insight_json` contract object.
- If you submit only the inner object or the old unwrapped payload, FastAPI will return `422`.

#### Example: upsert using the canonical sample request file

```bash
curl -s -X POST http://localhost:8000/reports \
  -H "Content-Type: application/json" \
  -d @backend/examples/post-report-request.json | python -m json.tool
```

PowerShell equivalent:

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://localhost:8000/reports" `
  -ContentType "application/json" `
  -Body (Get-Content -Raw .\backend\examples\post-report-request.json)
```

#### Example: generate a report (reuse by default)

```bash
curl -s -X POST http://localhost:8000/reports/generate \
  -H "Content-Type: application/json" \
  -d '{
    "report": {
      "game_id": 1,
      "team_id": 1,
      "persona_key": "team_analyst",
      "report_type": "postgame_insight",
      "headline": "Guardians postgame snapshot"
    }
  }' | python -m json.tool
```

Returns `"action": "inserted"` on first call, `"action": "reused"` on subsequent calls.
Add `"force": true` to the body to force regeneration (`"action": "regenerated"`).

#### Example: fetch the latest report for a team

```bash
curl -s "http://localhost:8000/reports/latest?team_id=1" | python -m json.tool
```

#### Example: fetch by id

```bash
curl -s http://localhost:8000/reports/1 | python -m json.tool
```

#### Example: fetch by logical identity

```bash
curl -s "http://localhost:8000/reports/by-identity?game_id=1&team_id=1&persona_key=team_analyst&report_type=postgame_insight" | python -m json.tool
```

#### Example: filter and paginate report listing

```bash
curl -s "http://localhost:8000/reports?game_id=1&team_id=1&limit=10&offset=0" | python -m json.tool
```

## Local data strategy (near term)

For this stage of the project, the primary local development path remains the deterministic manual/sample flow in `backend/app/report_service.py`, `backend/app/main.py`, and the API sample request files in `backend/examples/`.

This keeps API iteration predictable while the repo does not yet include a dedicated game/team ingestion pipeline.

The small service boundary in `backend/app/report_service.py` keeps report validation/persistence, report generation, and API route handling separate so future repo-native data sources can plug in without changing the current local-first workflow.

## SQL helper queries

Inspect the database directly using the helper file:

```bash
psql baseball_analyst -f backend/sql/generated_reports_queries.sql
```

Or open the file in **VS Code SQLTools**: right-click a query block → *Run Selected Query* to run individual statements.

Queries included:
1. Count all reports
2. List 20 most recent (id, identity, headline, created_at)
3. Find by identity tuple `(game_id, team_id, persona_key, report_type)`
4. Full-detail inspection with `row_age` — use this to confirm whether the last run inserted or updated the seed row
5. Delete the seed row so the next `python -m app.main` run performs a fresh insert
