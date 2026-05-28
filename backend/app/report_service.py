from copy import deepcopy
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.orm import Session

from app.models import GeneratedReport
from app.schemas import PostgameReportInsight

DEFAULT_SAMPLE_REPORT = {
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


@dataclass
class UpsertedReport:
    action: Literal["inserted", "updated"]
    report: GeneratedReport


def get_report_by_identity(
    session: Session,
    *,
    game_id: int,
    team_id: int,
    persona_key: str,
    report_type: str,
) -> GeneratedReport | None:
    return (
        session.query(GeneratedReport)
        .filter_by(
            game_id=game_id,
            team_id=team_id,
            persona_key=persona_key,
            report_type=report_type,
        )
        .first()
    )


def list_reports(
    session: Session,
    *,
    game_id: int | None = None,
    team_id: int | None = None,
    persona_key: str | None = None,
    report_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[GeneratedReport]:
    query = session.query(GeneratedReport)
    if game_id is not None:
        query = query.filter(GeneratedReport.game_id == game_id)
    if team_id is not None:
        query = query.filter(GeneratedReport.team_id == team_id)
    if persona_key is not None:
        query = query.filter(GeneratedReport.persona_key == persona_key)
    if report_type is not None:
        query = query.filter(GeneratedReport.report_type == report_type)
    return (
        query.order_by(GeneratedReport.created_at.desc(), GeneratedReport.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def upsert_report(
    session: Session,
    *,
    game_id: int,
    team_id: int,
    persona_key: str,
    report_type: str,
    insight_json: dict,
    headline: str | None = None,
    llm_output_markdown: str | None = None,
) -> UpsertedReport:
    row = get_report_by_identity(
        session,
        game_id=game_id,
        team_id=team_id,
        persona_key=persona_key,
        report_type=report_type,
    )
    action: Literal["inserted", "updated"]

    if row is None:
        row = GeneratedReport(
            game_id=game_id,
            team_id=team_id,
            persona_key=persona_key,
            report_type=report_type,
            insight_json=insight_json,
            headline=headline,
            llm_output_markdown=llm_output_markdown,
        )
        session.add(row)
        action = "inserted"
    else:
        row.insight_json = insight_json
        row.headline = headline
        row.llm_output_markdown = llm_output_markdown
        action = "updated"

    session.commit()
    session.refresh(row)
    return UpsertedReport(action=action, report=row)


def build_sample_postgame_insight(
    *,
    game_id: int = 1,
    team_id: int = 1,
) -> dict:
    sample_report = deepcopy(DEFAULT_SAMPLE_REPORT)
    sample_report["game_id"] = game_id
    sample_report["team"]["id"] = team_id
    insight = PostgameReportInsight.model_validate(sample_report)
    return insight.model_dump(mode="json")


def generate_sample_report(
    session: Session,
    *,
    game_id: int,
    team_id: int,
    persona_key: str,
    report_type: str,
    headline: str | None = None,
    llm_output_markdown: str | None = None,
) -> UpsertedReport:
    if report_type != "postgame_insight":
        raise ValueError(
            "sample generation currently supports only report_type='postgame_insight'"
        )

    return upsert_report(
        session,
        game_id=game_id,
        team_id=team_id,
        persona_key=persona_key,
        report_type=report_type,
        insight_json=build_sample_postgame_insight(game_id=game_id, team_id=team_id),
        headline=headline,
        llm_output_markdown=llm_output_markdown,
    )
