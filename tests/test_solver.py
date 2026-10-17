from datetime import date

from backend.engine import run_benchmarks
from backend.engine.types import DemandInput, EngineScenario, SupplyInput


def test_ortools_enforces_batch_moq_inventory_and_lead_time() -> None:
    scenario = EngineScenario(
        id="test", name="test", start_date=date(2026, 1, 1), horizon_periods=2,
        supplies=[
            SupplyInput(
                id=1, supplier_id="s1", supplier_name="Supplier", component="MCU", period=1,
                capacity=100, unit_cost=10, lead_time=0, minimum_order_quantity=50, batch_size=25,
            ),
            SupplyInput(
                id=2, supplier_id="late", supplier_name="Late", component="MCU", period=1,
                capacity=500, unit_cost=1, lead_time=2, minimum_order_quantity=0, batch_size=25,
            ),
        ],
        demands=[DemandInput(
            id=1, factory_id="f1", factory_name="Factory", component="MCU", period=1,
            quantity_requested=150, deadline=1, shortage_penalty=100, priority_score=5,
        )],
    )
    report = run_benchmarks(scenario, {"f1": 2.0}, disclosed_fields=15)
    privacy = next(item for item in report.strategies if item.strategy.startswith("Privacy-Aware"))
    assert sum(item.quantity for item in privacy.allocations) == 100
    assert privacy.unmet_demand == 50
    assert all(item.supplier_id != "late" for item in privacy.allocations)
    assert all(item.quantity % 25 == 0 and item.quantity >= 50 for item in privacy.allocations)


def test_full_information_is_authoritative_cost_baseline() -> None:
    scenario = EngineScenario(
        id="cost", name="cost", start_date=date(2026, 1, 1), horizon_periods=1,
        supplies=[SupplyInput(
            id=1, supplier_id="s", supplier_name="S", component="MCU", period=1,
            capacity=100, unit_cost=5, lead_time=0, minimum_order_quantity=0, batch_size=10,
        )],
        demands=[DemandInput(
            id=1, factory_id="f", factory_name="F", component="MCU", period=1,
            quantity_requested=100, deadline=1, shortage_penalty=50, priority_score=5,
        )],
    )
    report = run_benchmarks(scenario, {"f": 8}, 8)
    full = report.strategies[0]
    assert full.status == "OPTIMAL"
    assert full.total_network_cost == 1300
    assert full.optimality_gap == 0
