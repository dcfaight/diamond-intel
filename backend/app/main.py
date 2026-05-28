from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db import SessionLocal
from models import GeneratedReport
from schemas import PostgameReportInsight


def run() -> None:
    sample_report = {
        "game_id": 1,
        "team": {
            "id": 1,
            "name": "Cleveland Guardians",
            "abbreviation": "CLE",
        },
        "opponent": {
            "id": 2,
            "name": "Detroit Tigers",
            "abbreviation": "DET",
        },
        "game": {
            "date": "2026-05-28",
            "status": "Final",
            "score": {
                "team": 2,
                "opponent": 4,
            },
            "result": "loss",
            "venue": "Progressive Field",
        },
        "top_factors": [
            {
                "key": "missed_chances",
                "title": "Missed chances with runners on",
                "detail": "Cleveland failed to convert enough traffic into runs.",
            },
            {
                "key": "late_damage",
                "title": "Late damage decided the night",
                "detail": "Detroit produced the biggest swings after the middle innings.",
            },
        ],
        "player_trends": [
            {
                "player_name": "Jose Ramirez",
                "trend_type": "stock_up",
                "detail": "Reached base and remained the steadiest threat in the lineup.",
            }
        ],
        "watch_next": {
            "title": "What to watch next",
            "detail": "Watch whether Cleveland can generate more extra-base impact in the next game.",
        },
        "confidence": "medium",
        "generated_from": {
            "source": "manual_seed",
            "version": "v1",
        },
    }

    insight = PostgameReportInsight.model_validate(sample_report)

    session: Session = SessionLocal()
    try:
        row = GeneratedReport(
            game_id=insight.game_id,
            team_id=insight.team.id,
            persona_key="team_analyst",
            report_type="postgame_insight",
            insight_json=insight.model_dump(mode="json"),
            headline="Guardians postgame snapshot",
            llm_output_markdown=None,
        )
        session.add(row)
        session.commit()
        session.refresh(row)

        saved = session.get(GeneratedReport, row.id)
        print(f"Saved report id: {saved.id if saved else row.id}")
        print(saved.insight_json if saved else row.insight_json)
    except IntegrityError:
        session.rollback()
        # A uniqueness error can occur when inserting the same identity tuple again.
        print(
            "Insert failed due to database constraints. "
            "Ensure referenced game/team rows exist and avoid duplicate "
            "(game_id, team_id, persona_key, report_type) entries."
        )
    finally:
        session.close()


if __name__ == "__main__":
    run()
