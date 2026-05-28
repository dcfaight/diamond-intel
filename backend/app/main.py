from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.report_service import generate_sample_report


def run() -> None:
    # To verify update behavior locally: change the headline below or adjust
    # DEFAULT_SAMPLE_REPORT in app.report_service, then re-run.
    persona_key = "team_analyst"
    report_type = "postgame_insight"
    headline = "Guardians postgame snapshot"

    session: Session = SessionLocal()
    try:
        result = generate_sample_report(
            session,
            game_id=1,
            team_id=1,
            persona_key=persona_key,
            report_type=report_type,
            headline=headline,
        )
        row = result.report
        print(f"{result.action.capitalize()} report id: {row.id}")
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
