CREATE TABLE teams (
  id BIGSERIAL PRIMARY KEY,
  mlb_team_id INTEGER NOT NULL UNIQUE,
  name TEXT NOT NULL,
  abbreviation TEXT NOT NULL,
  city TEXT,
  league TEXT,
  division TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE games (
  id BIGSERIAL PRIMARY KEY,
  mlb_game_id BIGINT NOT NULL UNIQUE,
  season INTEGER NOT NULL,
  game_date DATE NOT NULL,
  start_time_utc TIMESTAMPTZ,
  status TEXT NOT NULL,
  game_type TEXT,
  venue_name TEXT,
  home_team_id BIGINT NOT NULL REFERENCES teams(id),
  away_team_id BIGINT NOT NULL REFERENCES teams(id),
  home_score INTEGER,
  away_score INTEGER,
  winning_team_id BIGINT REFERENCES teams(id),
  losing_team_id BIGINT REFERENCES teams(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE generated_reports (
  id BIGSERIAL PRIMARY KEY,
  game_id BIGINT NOT NULL REFERENCES games(id) ON DELETE CASCADE,
  team_id BIGINT NOT NULL REFERENCES teams(id),
  persona_key TEXT NOT NULL,
  report_type TEXT NOT NULL,
  insight_json JSONB NOT NULL,
  headline TEXT,
  llm_output_markdown TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (game_id, team_id, persona_key, report_type)
);
