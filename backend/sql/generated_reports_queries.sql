-- generated_reports_queries.sql
-- Local development helper queries for the generated_reports table.
-- Run against the baseball_analyst database:
--   psql baseball_analyst -f backend/sql/generated_reports_queries.sql
-- Or paste individual blocks into VS Code SQLTools.

-- ------------------------------------------------------------
-- 1. Count all reports
-- ------------------------------------------------------------
SELECT COUNT(*) AS total_reports
FROM generated_reports;


-- ------------------------------------------------------------
-- 2. List the 20 most recently created reports
-- ------------------------------------------------------------
SELECT
    id,
    game_id,
    team_id,
    persona_key,
    report_type,
    headline,
    created_at
FROM generated_reports
ORDER BY created_at DESC
LIMIT 20;


-- ------------------------------------------------------------
-- 3. Find a report by logical identity (game_id, team_id, persona_key, report_type)
--    Replace the values below with the ones you want to look up.
-- ------------------------------------------------------------
SELECT *
FROM generated_reports
WHERE game_id     = 1
  AND team_id     = 1
  AND persona_key = 'team_analyst'
  AND report_type = 'postgame_insight';


-- ------------------------------------------------------------
-- 4. Inspect full detail + insert-vs-update hint for the seed row.
--    age(created_at) will be close to 0 on the first run (insert)
--    and will keep growing on subsequent runs (update, row not recreated).
-- ------------------------------------------------------------
SELECT
    id,
    game_id,
    team_id,
    persona_key,
    report_type,
    headline,
    insight_json ->> 'confidence'          AS confidence,
    insight_json -> 'game' ->> 'result'    AS game_result,
    insight_json -> 'game' ->> 'date'      AS game_date,
    created_at,
    age(now(), created_at)                 AS row_age
FROM generated_reports
WHERE game_id     = 1
  AND team_id     = 1
  AND persona_key = 'team_analyst'
  AND report_type = 'postgame_insight';


-- ------------------------------------------------------------
-- 5. Delete the seeded / test row inserted by app.main
--    Run this, then re-run `python -m app.main` to test a fresh insert.
-- ------------------------------------------------------------
DELETE FROM generated_reports
WHERE game_id     = 1
  AND team_id     = 1
  AND persona_key = 'team_analyst'
  AND report_type = 'postgame_insight';
