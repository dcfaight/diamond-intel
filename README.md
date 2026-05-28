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

On the **first run** the output shows `Inserted`; every subsequent run shows `Updated`:

```
Inserted report id: 5
  Identity: game_id=1, team_id=1, persona_key='team_analyst', report_type='postgame_insight'
  Headline : 'Guardians postgame snapshot'
  Confidence: medium
  Result   : loss
```

### Verifying update behavior manually

1. Open `backend/app/main.py` and change the `headline` variable or the `"confidence"` field in `sample_report` (e.g. `"high"`).
2. Re-run the script — the output will say `Updated report id: <same id>` and reflect the new value.
3. Use query 4 in `backend/sql/generated_reports_queries.sql` to confirm in the database: the `row_age` column will be nonzero, confirming the row was not recreated.
4. To start fresh (test a clean insert), run query 5 from that file to delete the seed row, then re-run the script.

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
psql baseball_analyst -f backend/sql/generated_reports_queries.sql
```

Or open the file in **VS Code SQLTools**: right-click a query block → *Run Selected Query* to run individual statements.

Queries included:
1. Count all reports
2. List 20 most recent (id, identity, headline, created_at)
3. Find by identity tuple `(game_id, team_id, persona_key, report_type)`
4. Full-detail inspection with `row_age` — use this to confirm whether the last run inserted or updated the seed row
5. Delete the seed row so the next `python -m app.main` run performs a fresh insert
