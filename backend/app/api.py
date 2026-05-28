from datetime import datetime
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, ValidationError, field_validator, model_validator
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.main import upsert_report
from app.models import GeneratedReport
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

class ReportUpsertRequest(BaseModel):
    game_id: int
    team_id: int
    persona_key: str
    report_type: str
    insight_json: dict
    headline: str | None = None
    llm_output_markdown: str | None = None

    @field_validator("persona_key", "report_type")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("must not be empty")
        return cleaned

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
    """Create or update a generated postgame report (upsert on logical identity)."""
    existing = (
        db.query(GeneratedReport.id)
        .filter_by(
            game_id=body.game_id,
            team_id=body.team_id,
            persona_key=body.persona_key,
            report_type=body.report_type,
        )
        .first()
    )
    row = upsert_report(
        session=db,
        game_id=body.game_id,
        team_id=body.team_id,
        persona_key=body.persona_key,
        report_type=body.report_type,
        insight_json=body.insight_json,
        headline=body.headline,
        llm_output_markdown=body.llm_output_markdown,
    )
    action: Literal["inserted", "updated"] = "updated" if existing else "inserted"
    return ReportUpsertResponse(action=action, report=row)


@app.get("/reports/by-identity", response_model=ReportResponse)
def get_report_by_identity(
    game_id: int,
    team_id: int,
    persona_key: str,
    report_type: str,
    db: Session = Depends(get_db),
):
    """Fetch a single report by logical identity fields."""
    row = (
        db.query(GeneratedReport)
        .filter_by(
            game_id=game_id,
            team_id=team_id,
            persona_key=persona_key,
            report_type=report_type,
        )
        .first()
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
    query = db.query(GeneratedReport)
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
