import json
import pathlib
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import app, get_db
from app.api import ReportUpsertRequest
from app.models import Base, GeneratedReport
from app.report_service import build_sample_postgame_insight

_EXAMPLES_DIR = pathlib.Path(__file__).parent.parent / "examples"


class ReportsApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            future=True,
        )
        cls.TestSessionLocal = sessionmaker(
            bind=cls.engine,
            autoflush=False,
            autocommit=False,
            future=True,
        )

        def override_get_db():
            db = cls.TestSessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.clear()
        cls.engine.dispose()

    def setUp(self):
        Base.metadata.drop_all(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)

    def make_report_payload(self, **overrides):
        payload = {
            "game_id": 1,
            "team_id": 1,
            "persona_key": "team_analyst",
            "report_type": "postgame_insight",
            "headline": "Guardians postgame snapshot",
            "insight_json": build_sample_postgame_insight(game_id=1, team_id=1),
        }
        payload.update(overrides)
        return {"report": payload}

    def fetch_reports(self):
        with self.TestSessionLocal() as session:
            return session.query(GeneratedReport).order_by(GeneratedReport.id.asc()).all()

    def test_post_reports_requires_report_wrapper(self):
        response = self.client.post("/reports", json=self.make_report_payload()["report"])

        self.assertEqual(response.status_code, 422)
        self.assertIn("report", response.text)

    def test_post_reports_rejects_blank_persona_key(self):
        response = self.client.post(
            "/reports",
            json=self.make_report_payload(persona_key="   "),
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("must not be empty", response.text)

    def test_post_reports_rejects_blank_report_type(self):
        response = self.client.post(
            "/reports",
            json=self.make_report_payload(report_type="   "),
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("must not be empty", response.text)

    def test_post_reports_rejects_mismatched_game_id(self):
        payload = self.make_report_payload()
        payload["report"]["insight_json"]["game_id"] = 99

        response = self.client.post("/reports", json=payload)

        self.assertEqual(response.status_code, 422)
        self.assertIn("game_id must match insight_json.game_id", response.text)

    def test_post_reports_rejects_mismatched_team_id(self):
        payload = self.make_report_payload()
        payload["report"]["insight_json"]["team"]["id"] = 99

        response = self.client.post("/reports", json=payload)

        self.assertEqual(response.status_code, 422)
        self.assertIn("team_id must match insight_json.team.id", response.text)

    def test_post_reports_rejects_invalid_postgame_payload_shape(self):
        payload = self.make_report_payload()
        del payload["report"]["insight_json"]["team"]["name"]

        response = self.client.post("/reports", json=payload)

        self.assertEqual(response.status_code, 422)
        self.assertIn("invalid postgame_insight payload", response.text)

    def test_post_reports_upserts_existing_identity(self):
        first = self.client.post("/reports", json=self.make_report_payload())
        second_payload = self.make_report_payload(headline="Updated headline")
        second_payload["report"]["insight_json"]["confidence"] = "high"
        second = self.client.post("/reports", json=second_payload)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["action"], "inserted")
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["action"], "updated")
        self.assertEqual(first.json()["report"]["id"], second.json()["report"]["id"])

        rows = self.fetch_reports()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].headline, "Updated headline")
        self.assertEqual(rows[0].insight_json["confidence"], "high")

    def test_get_reports_lists_and_filters_rows(self):
        first = self.make_report_payload()
        second = self.make_report_payload(
            game_id=2,
            team_id=2,
            persona_key="player_analyst",
            headline="Second report",
            insight_json=build_sample_postgame_insight(game_id=2, team_id=2),
        )
        self.client.post("/reports", json=first)
        self.client.post("/reports", json=second)

        response = self.client.get("/reports", params={"team_id": 2})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["team_id"], 2)
        self.assertEqual(data[0]["persona_key"], "player_analyst")

    def test_get_report_by_identity_returns_row(self):
        created = self.client.post("/reports", json=self.make_report_payload()).json()

        response = self.client.get(
            "/reports/by-identity",
            params={
                "game_id": 1,
                "team_id": 1,
                "persona_key": "team_analyst",
                "report_type": "postgame_insight",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], created["report"]["id"])

    def test_get_report_by_identity_returns_404_for_missing_report(self):
        response = self.client.get(
            "/reports/by-identity",
            params={
                "game_id": 999,
                "team_id": 999,
                "persona_key": "missing",
                "report_type": "postgame_insight",
            },
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Report not found for identity")

    def test_generate_sample_report_persists_deterministic_payload(self):
        response = self.client.post(
            "/reports/generate-sample",
            json={
                "report": {
                    "game_id": 7,
                    "team_id": 3,
                    "persona_key": "team_analyst",
                    "report_type": "postgame_insight",
                    "headline": "Generated locally",
                }
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["action"], "inserted")
        self.assertEqual(body["report"]["game_id"], 7)
        self.assertEqual(body["report"]["team_id"], 3)
        self.assertEqual(body["report"]["insight_json"]["game_id"], 7)
        self.assertEqual(body["report"]["insight_json"]["team"]["id"], 3)
        self.assertEqual(
            body["report"]["insight_json"]["generated_from"]["source"], "manual_seed"
        )

    # ------------------------------------------------------------------
    # Canonical example contract test
    # ------------------------------------------------------------------

    def test_canonical_post_example_validates_against_request_model(self):
        """The canonical POST /reports example file must parse cleanly.

        This test is the anti-drift safeguard: any schema change that makes the
        canonical example invalid will fail CI immediately.
        """
        raw = (_EXAMPLES_DIR / "post-report-request.json").read_text()
        data = json.loads(raw)
        # Validate against the Pydantic model (raises if the shape is wrong)
        request = ReportUpsertRequest.model_validate(data)
        self.assertEqual(request.report.report_type, "postgame_insight")

    # ------------------------------------------------------------------
    # POST /reports/generate — reuse and force-regenerate behaviour
    # ------------------------------------------------------------------

    def _generate_payload(self, **overrides):
        payload = {
            "game_id": 5,
            "team_id": 5,
            "persona_key": "team_analyst",
            "report_type": "postgame_insight",
            "headline": "Generate test",
        }
        payload.update(overrides)
        return {"report": payload}

    def test_generate_report_inserts_when_no_existing_report(self):
        response = self.client.post(
            "/reports/generate", json=self._generate_payload()
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["action"], "inserted")
        self.assertEqual(body["report"]["game_id"], 5)

    def test_generate_report_reuses_existing_by_default(self):
        # First call inserts
        first = self.client.post("/reports/generate", json=self._generate_payload())
        self.assertEqual(first.json()["action"], "inserted")

        # Second call with same identity and no force should reuse
        second = self.client.post("/reports/generate", json=self._generate_payload())

        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["action"], "reused")
        self.assertEqual(first.json()["report"]["id"], second.json()["report"]["id"])

    def test_generate_report_force_regenerates(self):
        # Insert first
        first = self.client.post("/reports/generate", json=self._generate_payload())
        self.assertEqual(first.json()["action"], "inserted")

        # Force regenerate
        payload = self._generate_payload()
        payload["force"] = True
        second = self.client.post("/reports/generate", json=payload)

        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["action"], "regenerated")
        # Same row (same id), not a new one
        self.assertEqual(first.json()["report"]["id"], second.json()["report"]["id"])

    def test_generate_report_rejects_unsupported_report_type(self):
        response = self.client.post(
            "/reports/generate",
            json=self._generate_payload(report_type="unknown_type"),
        )

        self.assertEqual(response.status_code, 422)

    def test_generate_report_accepts_explicit_deterministic_local_source(self):
        response = self.client.post(
            "/reports/generate",
            json={
                **self._generate_payload(),
                "source": {
                    "mode": "deterministic_local",
                    "version": "v2-local",
                },
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["action"], "inserted")

    def test_generate_report_rejects_unknown_source_mode(self):
        response = self.client.post(
            "/reports/generate",
            json={
                **self._generate_payload(),
                "source": {
                    "mode": "external_ingestion",
                    "version": "v1",
                },
            },
        )

        self.assertEqual(response.status_code, 422)

    # ------------------------------------------------------------------
    # GET /reports/latest
    # ------------------------------------------------------------------

    def test_get_latest_report_returns_most_recent(self):
        self.client.post("/reports", json=self.make_report_payload())
        second = self.make_report_payload(
            game_id=3,
            team_id=3,
            persona_key="team_analyst",
            insight_json=build_sample_postgame_insight(game_id=3, team_id=3),
        )
        self.client.post("/reports", json=second)

        # Latest with no filter should be the second one (most recent)
        response = self.client.get("/reports/latest")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["game_id"], 3)

    def test_get_latest_report_filters_by_team(self):
        # Two reports for different teams
        self.client.post("/reports", json=self.make_report_payload())
        second = self.make_report_payload(
            game_id=4,
            team_id=4,
            persona_key="team_analyst",
            insight_json=build_sample_postgame_insight(game_id=4, team_id=4),
        )
        self.client.post("/reports", json=second)

        response = self.client.get("/reports/latest", params={"team_id": 1})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["team_id"], 1)

    def test_get_latest_report_returns_404_when_no_match(self):
        response = self.client.get(
            "/reports/latest", params={"team_id": 9999}
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "No matching report found")

    def test_get_latest_report_filters_by_persona(self):
        self.client.post("/reports", json=self.make_report_payload(persona_key="team_analyst"))
        self.client.post(
            "/reports",
            json=self.make_report_payload(
                game_id=8,
                team_id=8,
                persona_key="player_analyst",
                insight_json=build_sample_postgame_insight(game_id=8, team_id=8),
            ),
        )

        response = self.client.get(
            "/reports/latest",
            params={"persona_key": "team_analyst"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["persona_key"], "team_analyst")

    def test_get_latest_report_filters_by_report_type(self):
        self.client.post("/reports", json=self.make_report_payload(report_type="postgame_insight"))
        self.client.post(
            "/reports",
            json=self.make_report_payload(
                game_id=9,
                team_id=9,
                report_type="series_outlook",
                insight_json=build_sample_postgame_insight(game_id=9, team_id=9),
            ),
        )

        response = self.client.get(
            "/reports/latest",
            params={"report_type": "postgame_insight"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["report_type"], "postgame_insight")

    def test_get_latest_report_by_team_persona_type_returns_expected_row(self):
        self.client.post(
            "/reports",
            json=self.make_report_payload(
                game_id=10,
                team_id=3,
                persona_key="team_analyst",
                report_type="postgame_insight",
                insight_json=build_sample_postgame_insight(game_id=10, team_id=3),
            ),
        )
        self.client.post(
            "/reports",
            json=self.make_report_payload(
                game_id=11,
                team_id=3,
                persona_key="team_analyst",
                report_type="postgame_insight",
                insight_json=build_sample_postgame_insight(game_id=11, team_id=3),
            ),
        )

        response = self.client.get(
            "/reports/latest/by-team-persona-type",
            params={
                "team_id": 3,
                "persona_key": "team_analyst",
                "report_type": "postgame_insight",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["game_id"], 11)

    # ------------------------------------------------------------------
    # Summary retrieval endpoints
    # ------------------------------------------------------------------

    def test_get_latest_summary_returns_compact_fields(self):
        self.client.post("/reports", json=self.make_report_payload())

        response = self.client.get("/reports/latest/summary")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(
            set(body.keys()),
            {
                "id",
                "game_id",
                "team_id",
                "persona_key",
                "report_type",
                "headline",
                "created_at",
            },
        )

    def test_get_report_summaries_lists_compact_rows(self):
        self.client.post("/reports", json=self.make_report_payload())
        self.client.post(
            "/reports",
            json=self.make_report_payload(
                game_id=12,
                team_id=12,
                persona_key="player_analyst",
                insight_json=build_sample_postgame_insight(game_id=12, team_id=12),
            ),
        )

        response = self.client.get("/reports/summaries", params={"team_id": 12})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0]["team_id"], 12)
        self.assertNotIn("insight_json", body[0])


if __name__ == "__main__":
    unittest.main()
