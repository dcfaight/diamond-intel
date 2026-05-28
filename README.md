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
    main.py   ← seed / upsert entrypoint
    api.py    ← FastAPI routes
  examples/
    postgame-report-contract.json
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

Each run prints the upserted row's id and payload without failing on a duplicate.

## API

Start the development server:

```bash
cd backend && uvicorn app.api:app --reload
```

Interactive docs: <http://localhost:8000/docs>

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/reports` | Create or update a report (upsert) |
| `GET`  | `/reports/{id}` | Fetch a report by primary-key id |
| `GET`  | `/reports` | List reports; filter with `?game_id=&team_id=&persona_key=&report_type=` |

#### Example: upsert via curl

```bash
curl -s -X POST http://localhost:8000/reports \
  -H "Content-Type: application/json" \
  -d '{
    "game_id": 1,
    "team_id": 1,
    "persona_key": "team_analyst",
    "report_type": "postgame_insight",
    "insight_json": {"note": "test"},
    "headline": "Test headline"
  }' | python -m json.tool
```

#### Example: fetch by id

```bash
curl -s http://localhost:8000/reports/1 | python -m json.tool
```

#### Example: filter by game

```bash
curl -s "http://localhost:8000/reports?game_id=1&team_id=1" | python -m json.tool
```

## SQL helper queries

Inspect the database directly using the helper file:

```bash
psql baseball_analyst < backend/sql/generated_reports_queries.sql
# or interactively:
psql baseball_analyst -f backend/sql/generated_reports_queries.sql
```

Queries included: count, list recent, find by identity tuple, delete seed row.
