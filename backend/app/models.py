from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class GeneratedReport(Base):
    __tablename__ = "generated_reports"
    __table_args__ = (
        UniqueConstraint(
            "game_id",
            "team_id",
            "persona_key",
            "report_type",
            name="uq_generated_reports_identity",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    game_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    team_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    persona_key: Mapped[str] = mapped_column(Text, nullable=False)
    report_type: Mapped[str] = mapped_column(Text, nullable=False)
    insight_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    headline: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_output_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
