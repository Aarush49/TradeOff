from backend.api_schemas import DisruptionRequest, OptimizeRequest, ScenarioCreate
from backend.auth import DEMO_KEYS
from backend.main import create_app


def endpoint(app, path: str, method: str):
    return next(route.endpoint for route in app.routes if getattr(route, "path", None) == path and method in getattr(route, "methods", set()))


def test_full_optimization_and_disruption_flow(tmp_path) -> None:
    app = create_app(f"sqlite:///{(tmp_path / 'flow.db').as_posix()}")
    with app.state.session_factory() as session:
        created = endpoint(app, "/scenarios", "POST")(ScenarioCreate(), DEMO_KEYS["coordinator-demo-key"], session)
        initial = endpoint(app, "/optimize", "POST")(OptimizeRequest(scenario_id=created.id), DEMO_KEYS["coordinator-demo-key"], session)
        disrupted = endpoint(app, "/disrupt", "POST")(
            DisruptionRequest(scenario_id=created.id, preset="PRIMARY_CAPACITY_LOSS_40"),
            DEMO_KEYS["coordinator-demo-key"], session,
        )
    strategies = initial.report.strategies
    assert [item.strategy for item in strategies] == [
        "Full Information Optimum",
        "Privacy-Aware TradeOff Coordination",
        "First-Come, First-Served (FCFS)",
        "Priority-Only Allocation",
    ]
    assert disrupted.plan_id != initial.plan_id
    before = next(item for item in strategies if item.strategy.startswith("Privacy-Aware"))
    after = next(item for item in disrupted.report.strategies if item.strategy.startswith("Privacy-Aware"))
    assert after.total_network_cost != before.total_network_cost or after.unmet_demand != before.unmet_demand


def test_natural_language_disruption_uses_structured_override(tmp_path) -> None:
    app = create_app(f"sqlite:///{(tmp_path / 'nl.db').as_posix()}")
    with app.state.session_factory() as session:
        created = endpoint(app, "/scenarios", "POST")(ScenarioCreate(), DEMO_KEYS["coordinator-demo-key"], session)
        endpoint(app, "/disrupt", "POST")(
            DisruptionRequest(
                scenario_id=created.id, preset=None,
                natural_language="Simulate primary supplier losing 50% capacity on day 2",
            ), DEMO_KEYS["coordinator-demo-key"], session,
        )
        scenario = endpoint(app, "/scenarios/{scenario_id}", "GET")(created.id, DEMO_KEYS["coordinator-demo-key"], session)
    period_two = [
        item for item in scenario.supplies
        if item.supplier_id == "supplier-primary" and item.period == 2
    ]
    assert period_two[0].capacity == 175
