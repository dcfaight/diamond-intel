from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import GeneratedReport
from app.schemas import PostgameReportInsight


def upsert_report(
    session: Session,
    game_id: int,
    team_id: int,
    persona_key: str,
    report_type: str,
    insight_json: dict,
    headline: str | None = None,
    llm_output_markdown: str | None = None,
) -> GeneratedReport:
    """Insert or update a GeneratedReport row, keyed on the unique identity tuple."""
    stmt = (
        insert(GeneratedReport)
        .values(
            game_id=game_id,
            team_id=team_id,
            persona_key=persona_key,
            report_type=report_type,
            insight_json=insight_json,
            headline=headline,
            llm_output_markdown=llm_output_markdown,
        )
        .on_conflict_do_update(
            constraint="uq_generated_reports_identity",
            set_={
                "insight_json": insight_json,
                "headline": headline,
                "llm_output_markdown": llm_output_markdown,
            },
        )
        .returning(GeneratedReport)
    )
    result = session.execute(stmt)
    session.commit()
    return result.scalars().one()


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

    # To verify update behavior: change headline or confidence in sample_report above,
    # then re-run. The output will show "Updated" instead of "Inserted".
    persona_key = "team_analyst"
    report_type = "postgame_insight"
    headline = "Guardians postgame snapshot"

    session: Session = SessionLocal()
    try:
        existing = (
            session.query(GeneratedReport)
            .filter_by(
                game_id=insight.game_id,
                team_id=insight.team.id,
                persona_key=persona_key,
                report_type=report_type,
            )
            .first()
        )

        row = upsert_report(
            session=session,
            game_id=insight.game_id,
            team_id=insight.team.id,
            persona_key=persona_key,
            report_type=report_type,
            insight_json=insight.model_dump(mode="json"),
            headline=headline,
        )

        action = "Updated" if existing else "Inserted"
        print(f"{action} report id: {row.id}")
        print(
            f"  Identity: game_id={row.game_id}, team_id={row.team_id},"
            f" persona_key={row.persona_key!r}, report_type={row.report_type!r}"
        )
        print(f"  Headline : {row.headline!r}")
        print(f"  Confidence: {row.insight_json.get('confidence', '?')}")
        print(f"  Result   : {row.insight_json.get('game', {}).get('result', '?')}")
    finally:
        session.close()


if __name__ == "__main__":
    run()
