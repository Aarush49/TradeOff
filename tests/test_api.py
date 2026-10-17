from app.main import create_app


def endpoint(app, path: str, method: str):
    for route in app.routes:
        if getattr(route, "path", None) == path and method in getattr(route, "methods", set()):
            return route.endpoint
    raise AssertionError(f"Missing {method} {path}")


def test_api_contract_and_optimization(tmp_path) -> None:
    app = create_app(tmp_path / "audit.db")
    schema = app.openapi()
    assert "/optimize" in schema["paths"]
    result = app.state.coordinator.optimize()
    assert result.status == "optimal"
    assert app.state.audit_store.list_events()[0]["event_type"] == "optimization"


def test_disruption_replans(tmp_path) -> None:
    app = create_app(tmp_path / "audit.db")
    result = app.state.coordinator.replan("primary", 100, {})
    assert result.metrics.total_shortage == 700
    assert app.state.audit_store.list_events()[0]["event_type"] == "disruption_replan"


def test_private_participant_endpoint_is_registered(tmp_path) -> None:
    app = create_app(tmp_path / "audit.db")
    assert callable(endpoint(app, "/participants/{participant_id}", "GET"))
    assert callable(endpoint(app, "/audit", "GET"))
