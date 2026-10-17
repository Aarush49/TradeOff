import json
from pathlib import Path

from app.models import Scenario
from app.optimizer import optimize_scenario


def sample() -> Scenario:
    path = Path(__file__).parents[1] / "data" / "sample_scenario.json"
    return Scenario.model_validate(json.loads(path.read_text(encoding="utf-8")))


def test_optimizer_covers_sample_demand_at_minimum_cost() -> None:
    result = optimize_scenario(sample())
    assert result.status == "optimal"
    assert result.metrics.total_allocated == 1100
    assert result.metrics.total_shortage == 0
    assert result.metrics.total_network_cost == 34875.0
    assert result.metrics.baseline_network_cost == 34350.0
    assert result.metrics.optimality_gap > 0
    assert all(result.constraint_checks.values())


def test_disruption_creates_auditable_shortage() -> None:
    scenario = sample()
    scenario.suppliers[0].capacity = 350
    scenario.suppliers[1].capacity = 200
    result = optimize_scenario(scenario)
    assert result.metrics.total_allocated == 550
    assert result.metrics.total_shortage == 550
    assert result.metrics.shortage_cost > 0
    assert all(result.constraint_checks.values())


def test_deadline_blocks_late_supplier() -> None:
    scenario = sample()
    scenario.suppliers[0].lead_time_days = 20
    scenario.suppliers[1].lead_time_days = 20
    result = optimize_scenario(scenario)
    assert result.metrics.total_allocated == 0
    assert result.metrics.total_shortage == 1100
    assert result.constraint_checks["delivery_deadlines"]
