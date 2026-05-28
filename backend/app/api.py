from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.main import upsert_report
from app.models import GeneratedReport

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


class ReportResponse(BaseModel):
    id: int
    game_id: int
    team_id: int
    persona_key: str
    report_type: str
    insight_json: dict
    headline: str | None
    llm_output_markdown: str | None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.post("/reports", response_model=ReportResponse, status_code=200)
def create_or_update_report(
    body: ReportUpsertRequest,
    db: Session = Depends(get_db),
):
    """Create or update a generated postgame report (upsert on logical identity)."""
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
    db: Session = Depends(get_db),
):
    """List reports; optionally filter by any combination of identity fields."""
    query = db.query(GeneratedReport)
    if game_id is not None:
        query = query.filter(GeneratedReport.game_id == game_id)
    if team_id is not None:
        query = query.filter(GeneratedReport.team_id == team_id)
    if persona_key is not None:
        query = query.filter(GeneratedReport.persona_key == persona_key)
    if report_type is not None:
        query = query.filter(GeneratedReport.report_type == report_type)
    return query.all()
