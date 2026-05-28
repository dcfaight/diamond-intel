import json
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import GeneratedReport
from app.report_service import (
    ReportGenerationRequest,
    ReportGenerationSource,
    generate_report,
    generate_sample_report,
    get_latest_report as get_latest_report_record,
    get_report_by_identity as get_report_by_identity_record,
    list_reports as list_reports_records,
    upsert_report,
)
from app.schemas import PostgameReportInsight

app = FastAPI(title="Diamond Intel API")

# Load canonical POST /reports example once at startup so the Swagger UI and
# the example file share a single source of truth.
_EXAMPLES_DIR = Path(__file__).parent.parent / "examples"
_CANONICAL_POST_EXAMPLE: dict = json.loads(
    (_EXAMPLES_DIR / "post-report-request.json").read_text()
)


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
        "json_schema_extra": {"example": _CANONICAL_POST_EXAMPLE}
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


class ReportGenerationSourcePayload(BaseModel):
    mode: Literal["deterministic_local"] = "deterministic_local"
    version: str = "v1"

    @field_validator("version")
    @classmethod
    def validate_non_empty_version(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("must not be empty")
        return cleaned


class GenerateReportRequest(BaseModel):
    """Request body for POST /reports/generate.

    Accepts a logical report identity plus an optional ``force`` flag.
    When ``force`` is False (the default) an existing report for the identity
    is returned unchanged (action="reused").  Set ``force=true`` to rebuild
    from local data and overwrite the stored row (action="regenerated").
    """

    report: ReportIdentityPayload
    force: bool = False
    source: ReportGenerationSourcePayload = Field(
        default_factory=ReportGenerationSourcePayload
    )

    @model_validator(mode="after")
    def validate_supported_report_type(self):
        if self.report.report_type != "postgame_insight":
            raise ValueError(
                "generation currently supports only report_type='postgame_insight'"
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
    action: Literal["inserted", "updated", "reused", "regenerated"]
    report: ReportResponse


class ReportSummaryResponse(BaseModel):
    id: int
    game_id: int
    team_id: int
    persona_key: str
    report_type: str
    headline: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


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


@app.post("/reports/generate", response_model=ReportUpsertResponse, status_code=200)
def generate_report_endpoint(
    body: GenerateReportRequest,
    db: Session = Depends(get_db),
):
    """Generate a report from local data, honouring the reuse/regenerate policy.

    - ``force=false`` (default): return the stored report unchanged if it already
      exists (action="reused").
    - ``force=true``: rebuild from local data and overwrite the row
      (action="regenerated"), or insert if none exists (action="inserted").
    """
    result = generate_report(
        db,
        request=ReportGenerationRequest(
            game_id=body.report.game_id,
            team_id=body.report.team_id,
            persona_key=body.report.persona_key,
            report_type=body.report.report_type,
            headline=body.report.headline,
            llm_output_markdown=body.report.llm_output_markdown,
            source=ReportGenerationSource(
                mode=body.source.mode,
                version=body.source.version,
            ),
        ),
        force_regenerate=body.force,
    )
    return ReportUpsertResponse(action=result.action, report=result.report)


@app.get("/reports/latest", response_model=ReportResponse)
def get_latest_report(
    game_id: int | None = None,
    team_id: int | None = None,
    persona_key: str | None = None,
    report_type: str | None = None,
    db: Session = Depends(get_db),
):
    """Return the single most-recently created report matching the given filters.

    Useful for quickly checking the latest report for a team, persona, or game
    without paginating through the full list.  Returns 404 if no matching report
    exists.
    """
    row = get_latest_report_record(
        db,
        game_id=game_id,
        team_id=team_id,
        persona_key=persona_key,
        report_type=report_type,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="No matching report found")
    return row


@app.get("/reports/latest/by-team/{team_id}", response_model=ReportResponse)
def get_latest_report_by_team(
    team_id: int,
    db: Session = Depends(get_db),
):
    """Return the latest report for a single team."""
    row = get_latest_report_record(db, team_id=team_id)
    if row is None:
        raise HTTPException(status_code=404, detail="No matching report found")
    return row


@app.get("/reports/latest/by-persona/{persona_key}", response_model=ReportResponse)
def get_latest_report_by_persona(
    persona_key: str,
    db: Session = Depends(get_db),
):
    """Return the latest report for a persona key."""
    row = get_latest_report_record(db, persona_key=persona_key)
    if row is None:
        raise HTTPException(status_code=404, detail="No matching report found")
    return row


@app.get("/reports/latest/by-report-type/{report_type}", response_model=ReportResponse)
def get_latest_report_by_report_type(
    report_type: str,
    db: Session = Depends(get_db),
):
    """Return the latest report for a report type."""
    row = get_latest_report_record(db, report_type=report_type)
    if row is None:
        raise HTTPException(status_code=404, detail="No matching report found")
    return row


@app.get("/reports/latest/by-team-persona-type", response_model=ReportResponse)
def get_latest_report_by_team_persona_type(
    team_id: int,
    persona_key: str,
    report_type: str,
    db: Session = Depends(get_db),
):
    """Return the latest report for an explicit team/persona/report_type tuple."""
    row = get_latest_report_record(
        db,
        team_id=team_id,
        persona_key=persona_key,
        report_type=report_type,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="No matching report found")
    return row


@app.get("/reports/latest/summary", response_model=ReportSummaryResponse)
def get_latest_report_summary(
    game_id: int | None = None,
    team_id: int | None = None,
    persona_key: str | None = None,
    report_type: str | None = None,
    db: Session = Depends(get_db),
):
    """Return compact latest-report metadata for local inspection/UI list usage."""
    row = get_latest_report_record(
        db,
        game_id=game_id,
        team_id=team_id,
        persona_key=persona_key,
        report_type=report_type,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="No matching report found")
    return row


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


@app.get("/reports/summaries", response_model=list[ReportSummaryResponse])
def find_report_summaries(
    game_id: int | None = None,
    team_id: int | None = None,
    persona_key: str | None = None,
    report_type: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """List compact report metadata with the same filters as GET /reports."""
    return list_reports_records(
        db,
        game_id=game_id,
        team_id=team_id,
        persona_key=persona_key,
        report_type=report_type,
        limit=limit,
        offset=offset,
    )


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
