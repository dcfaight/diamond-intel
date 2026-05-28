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
    main.py
  examples/
    postgame-report-contract.json
  requirements.txt
sql/
  schema.sql
README.md
```

## Local setup

1. Create a PostgreSQL database named `baseball_analyst`.
2. Run `/tmp/workspace/dcfaight/diamond-intel/sql/schema.sql` against that database.
3. Install dependencies:
   - `pip install -r /tmp/workspace/dcfaight/diamond-intel/backend/requirements.txt`
4. Set the `DATABASE_URL` environment variable (or use the default fallback in `db.py`).
5. Run:
   - `python /tmp/workspace/dcfaight/diamond-intel/backend/app/main.py`
