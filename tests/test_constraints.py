from app.models import Factory, Scenario, Supplier
from app.optimizer import optimize_scenario


def test_higher_shortage_penalty_gets_scarce_capacity_first() -> None:
    scenario = Scenario(
        factories=[
            Factory(id="critical", name="Critical", demand=100, shortage_penalty=100),
            Factory(id="standard", name="Standard", demand=100, shortage_penalty=20),
        ],
        suppliers=[Supplier(id="only", name="Only", capacity=100, unit_cost=5)],
    )
    result = optimize_scenario(scenario)
    critical = next(item for item in result.factory_outcomes if item.factory_id == "critical")
    standard = next(item for item in result.factory_outcomes if item.factory_id == "standard")
    assert critical.allocated == 100
    assert standard.shortage == 100


def test_capacity_never_exceeded() -> None:
    scenario = Scenario(
        factories=[Factory(id="f", name="Factory", demand=250, shortage_penalty=50)],
        suppliers=[Supplier(id="s", name="Supplier", capacity=75, unit_cost=10)],
    )
    result = optimize_scenario(scenario)
    assert sum(item.quantity for item in result.allocations) == 75
    assert result.constraint_checks["supplier_capacity"]
