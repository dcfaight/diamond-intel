from datetime import datetime
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import GeneratedReport
from app.report_service import (
    generate_sample_report,
    get_report_by_identity as get_report_by_identity_record,
    list_reports as list_reports_records,
    upsert_report,
)
from app.schemas import PostgameReportInsight

app = FastAPI(title="Diamond Intel API")


# ---------------------------------------------------------------------------
# Dependency
# ---------------------------------------------------------------------------

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class ReportIdentityPayload(BaseModel):
    game_id: int
    team_id: int
    persona_key: str
    report_type: str
    headline: str | None = None
    llm_output_markdown: str | None = None

    @field_validator("persona_key", "report_type")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("must not be empty")
        return cleaned


class ReportPayload(ReportIdentityPayload):
    insight_json: dict = Field(
        description=(
            "Inner postgame insight payload (validated against "
            "backend/examples/postgame-report-contract.json for "
            "report_type='postgame_insight')."
        )
    )

    @model_validator(mode="after")
    def validate_postgame_payload(self):
        if self.report_type != "postgame_insight":
            return self

        try:
            insight = PostgameReportInsight.model_validate(self.insight_json)
        except ValidationError as exc:
            raise ValueError(f"invalid postgame_insight payload: {exc}") from exc

        if insight.game_id != self.game_id:
            raise ValueError("game_id must match insight_json.game_id")
        if insight.team.id != self.team_id:
            raise ValueError("team_id must match insight_json.team.id")
        return self


class ReportUpsertRequest(BaseModel):
    report: ReportPayload

    model_config = {
        "json_schema_extra": {
            "example": {
                "report": {
                    "game_id": 1,
                    "team_id": 1,
                    "persona_key": "team_analyst",
                    "report_type": "postgame_insight",
                    "headline": "Guardians postgame snapshot",
                    "insight_json": {
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
                            "score": {"team": 2, "opponent": 4},
                            "result": "loss",
                            "venue": "Progressive Field",
                        },
                        "top_factors": [
                            {
                                "key": "missed_chances",
                                "title": "Missed chances with runners on",
                                "detail": (
                                    "Cleveland failed to convert enough traffic "
                                    "into runs."
                                ),
                            }
                        ],
                        "player_trends": [
                            {
                                "player_name": "Jose Ramirez",
                                "trend_type": "stock_up",
                                "detail": (
                                    "Reached base and remained the steadiest "
                                    "threat in the lineup."
                                ),
                            }
                        ],
                        "watch_next": {
                            "title": "What to watch next",
                            "detail": (
                                "Watch whether Cleveland can generate more "
                                "extra-base impact in the next game."
                            ),
                        },
                        "confidence": "medium",
                        "generated_from": {"source": "manual_seed", "version": "v1"},
                    },
                }
            }
        }
    }


class SampleReportGenerationRequest(BaseModel):
    report: ReportIdentityPayload

    @model_validator(mode="after")
    def validate_supported_report_type(self):
        if self.report.report_type != "postgame_insight":
            raise ValueError(
                "sample generation currently supports only report_type='postgame_insight'"
            )
        return self


class ReportResponse(BaseModel):
    id: int
    game_id: int
    team_id: int
    persona_key: str
    report_type: str
    insight_json: dict
    headline: str | None
    llm_output_markdown: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ReportUpsertResponse(BaseModel):
    action: Literal["inserted", "updated"]
    report: ReportResponse


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.post("/reports", response_model=ReportUpsertResponse, status_code=200)
def create_or_update_report(
    body: ReportUpsertRequest,
    db: Session = Depends(get_db),
):
    """Create or update a generated postgame report using body shape {'report': {...}}."""
    result = upsert_report(
        db,
        game_id=body.report.game_id,
        team_id=body.report.team_id,
        persona_key=body.report.persona_key,
        report_type=body.report.report_type,
        insight_json=body.report.insight_json,
        headline=body.report.headline,
        llm_output_markdown=body.report.llm_output_markdown,
    )
    return ReportUpsertResponse(action=result.action, report=result.report)


@app.post("/reports/generate-sample", response_model=ReportUpsertResponse, status_code=200)
def create_sample_report(
    body: SampleReportGenerationRequest,
    db: Session = Depends(get_db),
):
    """Generate and persist the deterministic local sample report."""
    result = generate_sample_report(
        db,
        game_id=body.report.game_id,
        team_id=body.report.team_id,
        persona_key=body.report.persona_key,
        report_type=body.report.report_type,
        headline=body.report.headline,
        llm_output_markdown=body.report.llm_output_markdown,
    )
    return ReportUpsertResponse(action=result.action, report=result.report)


@app.get("/reports/by-identity", response_model=ReportResponse)
def get_report_by_identity(
    game_id: int,
    team_id: int,
    persona_key: str,
    report_type: str,
    db: Session = Depends(get_db),
):
    """Fetch a single report by logical identity fields."""
    row = get_report_by_identity_record(
        db,
        game_id=game_id,
        team_id=team_id,
        persona_key=persona_key,
        report_type=report_type,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Report not found for identity")
    return row


@app.get("/reports/{report_id}", response_model=ReportResponse)
def get_report_by_id(report_id: int, db: Session = Depends(get_db)):
    """Fetch a report by its primary-key id."""
    row = db.get(GeneratedReport, report_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return row


@app.get("/reports", response_model=list[ReportResponse])
def find_reports(
    game_id: int | None = None,
    team_id: int | None = None,
    persona_key: str | None = None,
    report_type: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """List reports with optional filters and stable newest-first ordering."""
    return list_reports_records(
        db,
        game_id=game_id,
        team_id=team_id,
        persona_key=persona_key,
        report_type=report_type,
        limit=limit,
        offset=offset,
    )
