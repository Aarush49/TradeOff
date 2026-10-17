from fastapi import HTTPException
import pytest

from backend.api_schemas import ScenarioCreate, OptimizeRequest
from backend.auth import DEMO_KEYS
from backend.main import create_app
from backend.services.scenarios import APPROVED_DEMAND_FIELDS, APPROVED_SUPPLY_FIELDS


def endpoint(app, path: str, method: str):
    return next(route.endpoint for route in app.routes if getattr(route, "path", None) == path and method in getattr(route, "methods", set()))


def test_factory_a_cannot_access_factory_b_private_data(tmp_path) -> None:
    app = create_app(f"sqlite:///{(tmp_path / 'privacy.db').as_posix()}")
    private_route = endpoint(app, "/participants/{participant_id}/private-data", "GET")
    with app.state.session_factory() as session, pytest.raises(HTTPException) as error:
        private_route("factory-b", DEMO_KEYS["factory-a-demo-key"], session)
    assert error.value.status_code == 403
    assert "own private data" in error.value.detail


def test_optimization_audit_precisely_records_disclosures(tmp_path) -> None:
    app = create_app(f"sqlite:///{(tmp_path / 'audit.db').as_posix()}")
    with app.state.session_factory() as session:
        scenario = endpoint(app, "/scenarios", "POST")(ScenarioCreate(), DEMO_KEYS["coordinator-demo-key"], session)
        optimized = endpoint(app, "/optimize", "POST")(OptimizeRequest(scenario_id=scenario.id), DEMO_KEYS["coordinator-demo-key"], session)
        audit = endpoint(app, "/audit-log", "GET")(DEMO_KEYS["auditor-demo-key"], session)
        factory_view = endpoint(app, "/plans/{plan_id}/participant-summary", "GET")(
            optimized.plan_id, DEMO_KEYS["factory-a-demo-key"], session
        )
    disclosures = [item for item in audit if item.plan_id == optimized.plan_id and item.action == "OPTIMIZATION_DISCLOSURE"]
    assert len(disclosures) == 4
    by_target = {item.target_participant_id: item.fields_disclosed for item in disclosures}
    assert by_target["factory-a"] == APPROVED_DEMAND_FIELDS
    assert by_target["factory-b"] == APPROVED_DEMAND_FIELDS
    assert by_target["supplier-primary"] == APPROVED_SUPPLY_FIELDS
    assert by_target["supplier-alt"] == APPROVED_SUPPLY_FIELDS
    assert "unit_production_cost" not in {field for fields in by_target.values() for field in fields}
    assert list(factory_view) == ["factory-a"]
