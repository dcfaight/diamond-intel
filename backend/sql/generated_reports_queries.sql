-- generated_reports_queries.sql
-- Local development helper queries for the generated_reports table.
-- Run these against the baseball_analyst database.

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
-- 4. Delete the seeded / test row inserted by app.main
--    (safe to re-run after deleting to test idempotency)
-- ------------------------------------------------------------
DELETE FROM generated_reports
WHERE game_id     = 1
  AND team_id     = 1
  AND persona_key = 'team_analyst'
  AND report_type = 'postgame_insight';
