from __future__ import annotations

import time
from math import ceil

from ortools.sat.python import cp_model

from .types import Allocation, EngineScenario, StrategyMetrics


CENTS = 100


def solve_optimal(
    scenario: EngineScenario,
    *,
    strategy: str,
    private_production_costs: dict[str, float] | None = None,
    disclosed_fields: int = 0,
) -> StrategyMetrics:
    started = time.perf_counter()
    model = cp_model.CpModel()
    private_production_costs = private_production_costs or {}
    decisions: dict[tuple[int, int], cp_model.IntVar] = {}
    active: dict[tuple[int, int], cp_model.IntVar] = {}
    shortage: dict[int, cp_model.IntVar] = {}

    for supply in scenario.supplies:
        batch = max(supply.batch_size, 1)
        max_batches = supply.capacity // batch
        for demand in scenario.demands:
            if supply.component != demand.component or supply.period + supply.lead_time > demand.deadline:
                continue
            key = (supply.id, demand.id)
            decisions[key] = model.new_int_var(0, max_batches, f"x_{supply.id}_{demand.id}")
            active[key] = model.new_bool_var(f"y_{supply.id}_{demand.id}")
            minimum_batches = ceil(supply.minimum_order_quantity / batch) if supply.minimum_order_quantity else 0
            model.add(decisions[key] <= max_batches * active[key])
            if minimum_batches:
                model.add(decisions[key] >= minimum_batches * active[key])

    # Inventory balance: unused supply carries forward within supplier/component.
    for supplier_id in {item.supplier_id for item in scenario.supplies}:
        for component in {item.component for item in scenario.supplies if item.supplier_id == supplier_id}:
            prior_inventory = 0
            for period in range(1, scenario.horizon_periods + 1):
                arrivals = sum(
                    item.capacity
                    for item in scenario.supplies
                    if item.supplier_id == supplier_id and item.component == component and item.period == period
                )
                shipped_terms = []
                for supply in scenario.supplies:
                    if supply.supplier_id == supplier_id and supply.component == component and supply.period == period:
                        shipped_terms.extend(
                            decisions[(supply.id, demand.id)] * max(supply.batch_size, 1)
                            for demand in scenario.demands
                            if (supply.id, demand.id) in decisions
                        )
                inventory = model.new_int_var(0, 10_000_000, f"inv_{supplier_id}_{component}_{period}")
                model.add(inventory == prior_inventory + arrivals - sum(shipped_terms))
                prior_inventory = inventory

    objective_terms = []
    for demand in scenario.demands:
        shortage[demand.id] = model.new_int_var(0, demand.quantity_requested, f"short_{demand.id}")
        received = []
        for supply in scenario.supplies:
            key = (supply.id, demand.id)
            if key not in decisions:
                continue
            quantity = decisions[key] * max(supply.batch_size, 1)
            received.append(quantity)
            cost = supply.unit_cost + private_production_costs.get(demand.factory_id, 0)
            objective_terms.append(quantity * round(cost * CENTS))
        model.add(sum(received) + shortage[demand.id] == demand.quantity_requested)
        objective_terms.append(shortage[demand.id] * round(demand.shortage_penalty * CENTS))

    model.minimize(sum(objective_terms))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10
    solver.parameters.num_search_workers = 8
    status = solver.solve(model)
    feasible = status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    allocations: list[Allocation] = []
    source_cost = 0.0
    production_cost = 0.0
    for supply in scenario.supplies:
        for demand in scenario.demands:
            key = (supply.id, demand.id)
            if key not in decisions or not feasible:
                continue
            quantity = solver.value(decisions[key]) * max(supply.batch_size, 1)
            if not quantity:
                continue
            source_cost += quantity * supply.unit_cost
            production_cost += quantity * private_production_costs.get(demand.factory_id, 0)
            allocations.append(
                Allocation(
                    supplier_id=supply.supplier_id,
                    supplier_name=supply.supplier_name,
                    factory_id=demand.factory_id,
                    factory_name=demand.factory_name,
                    component=demand.component,
                    quantity=quantity,
                    ship_period=supply.period,
                    delivery_period=supply.period + supply.lead_time,
                    unit_cost=supply.unit_cost,
                )
            )
    shortages = {
        demand.factory_id + ":" + demand.component + f":P{demand.period}": solver.value(shortage[demand.id]) if feasible else demand.quantity_requested
        for demand in scenario.demands
    }
    shortage_cost = sum(
        shortages[demand.factory_id + ":" + demand.component + f":P{demand.period}"] * demand.shortage_penalty
        for demand in scenario.demands
    )
    return StrategyMetrics(
        strategy=strategy,
        status="OPTIMAL" if status == cp_model.OPTIMAL else ("FEASIBLE" if feasible else "INFEASIBLE"),
        total_network_cost=round(source_cost + production_cost + shortage_cost, 2),
        unmet_demand=sum(shortages.values()),
        disclosed_fields=disclosed_fields,
        solve_time_ms=round((time.perf_counter() - started) * 1000, 2),
        allocations=allocations,
        shortages=shortages,
    )


def solve_greedy(
    scenario: EngineScenario,
    *,
    strategy: str,
    by_priority: bool,
    private_production_costs: dict[str, float],
) -> StrategyMetrics:
    started = time.perf_counter()
    inventory = {item.id: item.capacity for item in scenario.supplies}
    demands = sorted(
        scenario.demands,
        key=(lambda item: (-item.priority_score, item.period, item.id)) if by_priority else (lambda item: (item.period, item.id)),
    )
    allocations: list[Allocation] = []
    shortages: dict[str, int] = {}
    for demand in demands:
        remaining = demand.quantity_requested
        eligible = sorted(
            [item for item in scenario.supplies if item.component == demand.component and item.period + item.lead_time <= demand.deadline],
            key=lambda item: (item.period, item.unit_cost),
        )
        for supply in eligible:
            batch = max(supply.batch_size, 1)
            quantity = min(remaining, inventory[supply.id])
            quantity -= quantity % batch
            if 0 < quantity < supply.minimum_order_quantity:
                continue
            if quantity <= 0:
                continue
            inventory[supply.id] -= quantity
            remaining -= quantity
            allocations.append(Allocation(
                supplier_id=supply.supplier_id, supplier_name=supply.supplier_name,
                factory_id=demand.factory_id, factory_name=demand.factory_name,
                component=demand.component, quantity=quantity, ship_period=supply.period,
                delivery_period=supply.period + supply.lead_time, unit_cost=supply.unit_cost,
            ))
        shortages[demand.factory_id + ":" + demand.component + f":P{demand.period}"] = remaining
    source_cost = sum(item.quantity * item.unit_cost for item in allocations)
    production_cost = sum(item.quantity * private_production_costs.get(item.factory_id, 0) for item in allocations)
    shortage_cost = sum(
        shortages[item.factory_id + ":" + item.component + f":P{item.period}"] * item.shortage_penalty
        for item in scenario.demands
    )
    return StrategyMetrics(
        strategy=strategy, status="HEURISTIC", total_network_cost=round(source_cost + production_cost + shortage_cost, 2),
        unmet_demand=sum(shortages.values()), disclosed_fields=0,
        solve_time_ms=round((time.perf_counter() - started) * 1000, 2), allocations=allocations, shortages=shortages,
    )
