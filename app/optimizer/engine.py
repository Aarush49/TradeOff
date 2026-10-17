from __future__ import annotations

import heapq
import time
from dataclasses import dataclass
from math import inf
from uuid import uuid4

from app.agents import FactoryAgent, SupplierAgent
from app.models import Allocation, FactoryOutcome, Metrics, OptimizationResult, Scenario


COST_SCALE = 100


@dataclass
class Edge:
    to: int
    reverse: int
    capacity: int
    cost: int
    original_capacity: int


class MinCostFlow:
    def __init__(self, size: int) -> None:
        self.graph: list[list[Edge]] = [[] for _ in range(size)]

    def add_edge(self, source: int, target: int, capacity: int, cost: int) -> int:
        index = len(self.graph[source])
        forward = Edge(target, len(self.graph[target]), capacity, cost, capacity)
        reverse = Edge(source, index, 0, -cost, 0)
        self.graph[source].append(forward)
        self.graph[target].append(reverse)
        return index

    def solve(self, source: int, sink: int, required_flow: int) -> tuple[int, int]:
        size = len(self.graph)
        potential = [0] * size
        total_flow = 0
        total_cost = 0

        while total_flow < required_flow:
            distance = [inf] * size
            parent_node = [-1] * size
            parent_edge = [-1] * size
            distance[source] = 0
            queue: list[tuple[float, int]] = [(0, source)]

            while queue:
                current_distance, node = heapq.heappop(queue)
                if current_distance != distance[node]:
                    continue
                for edge_index, edge in enumerate(self.graph[node]):
                    if edge.capacity <= 0:
                        continue
                    candidate = current_distance + edge.cost + potential[node] - potential[edge.to]
                    if candidate < distance[edge.to]:
                        distance[edge.to] = candidate
                        parent_node[edge.to] = node
                        parent_edge[edge.to] = edge_index
                        heapq.heappush(queue, (candidate, edge.to))

            if distance[sink] == inf:
                break
            for node in range(size):
                if distance[node] < inf:
                    potential[node] += int(distance[node])

            amount = required_flow - total_flow
            node = sink
            while node != source:
                previous = parent_node[node]
                if previous < 0:
                    return total_flow, total_cost
                edge = self.graph[previous][parent_edge[node]]
                amount = min(amount, edge.capacity)
                node = previous

            node = sink
            while node != source:
                previous = parent_node[node]
                edge = self.graph[previous][parent_edge[node]]
                edge.capacity -= amount
                self.graph[node][edge.reverse].capacity += amount
                total_cost += amount * edge.cost
                node = previous
            total_flow += amount

        return total_flow, total_cost


def _money(value: float) -> int:
    return round(value * COST_SCALE)


def optimize_scenario(
    scenario: Scenario,
    *,
    include_private_costs: bool = False,
    calculate_baseline: bool = True,
) -> OptimizationResult:
    started = time.perf_counter()
    supplier_count = len(scenario.suppliers)
    factory_count = len(scenario.factories)
    source = 0
    supplier_offset = 1
    factory_offset = supplier_offset + supplier_count
    sink = factory_offset + factory_count
    network = MinCostFlow(sink + 1)
    tracked: list[tuple[int, int, int, int, float]] = []
    shortages: list[tuple[int, int, int]] = []

    for supplier_index, supplier in enumerate(scenario.suppliers):
        supplier_node = supplier_offset + supplier_index
        network.add_edge(source, supplier_node, supplier.capacity, 0)
        for factory_index, factory in enumerate(scenario.factories):
            if supplier.lead_time_days > factory.deadline_days:
                continue
            factory_node = factory_offset + factory_index
            shipping = scenario.shipping_costs.get(supplier.id, {}).get(factory.id, 0.0)
            unit_cost = supplier.unit_cost + shipping
            optimization_cost = unit_cost + (factory.production_cost if include_private_costs else 0)
            edge_index = network.add_edge(
                supplier_node,
                factory_node,
                min(supplier.capacity, factory.demand),
                _money(optimization_cost),
            )
            tracked.append((supplier_node, edge_index, supplier_index, factory_index, unit_cost))

    for factory_index, factory in enumerate(scenario.factories):
        factory_node = factory_offset + factory_index
        edge_index = network.add_edge(source, factory_node, factory.demand, _money(factory.shortage_penalty))
        shortages.append((source, edge_index, factory_index))
        network.add_edge(factory_node, sink, factory.demand, 0)

    total_demand = sum(factory.demand for factory in scenario.factories)
    flow, scaled_cost = network.solve(source, sink, total_demand)
    allocations: list[Allocation] = []
    allocated_by_factory = {factory.id: 0 for factory in scenario.factories}
    source_cost = 0.0

    for node, edge_index, supplier_index, factory_index, unit_cost in tracked:
        edge = network.graph[node][edge_index]
        quantity = edge.original_capacity - edge.capacity
        if quantity <= 0:
            continue
        supplier = scenario.suppliers[supplier_index]
        factory = scenario.factories[factory_index]
        allocated_by_factory[factory.id] += quantity
        line_cost = round(quantity * unit_cost, 2)
        source_cost += line_cost
        allocations.append(
            Allocation(
                supplier_id=supplier.id,
                supplier_name=supplier.name,
                factory_id=factory.id,
                factory_name=factory.name,
                quantity=quantity,
                unit_cost=unit_cost,
                total_cost=line_cost,
            )
        )

    outcomes: list[FactoryOutcome] = []
    shortage_cost = 0.0
    production_cost = 0.0
    for factory in scenario.factories:
        allocated = allocated_by_factory[factory.id]
        shortage = factory.demand - allocated
        shortage_cost += shortage * factory.shortage_penalty
        production_cost += allocated * factory.production_cost
        outcomes.append(
            FactoryOutcome(
                factory_id=factory.id,
                demand=factory.demand,
                allocated=allocated,
                shortage=shortage,
                service_level=round((allocated / factory.demand * 100) if factory.demand else 100.0, 2),
            )
        )

    messages = [FactoryAgent(item).request() for item in scenario.factories]
    messages += [SupplierAgent(item).offer() for item in scenario.suppliers]
    disclosed = sum(len(message.approved_payload) for message in messages)
    withheld = len(scenario.factories) * 2 + len(scenario.suppliers) * 1
    total_shortage = sum(item.shortage for item in outcomes)
    actual_total_cost = round(source_cost + production_cost + shortage_cost, 2)
    if calculate_baseline:
        baseline = optimize_scenario(
            scenario,
            include_private_costs=True,
            calculate_baseline=False,
        )
        baseline_cost = baseline.metrics.total_network_cost
    else:
        baseline_cost = actual_total_cost
    gap = (
        ((actual_total_cost - baseline_cost) / baseline_cost * 100)
        if baseline_cost
        else 0.0
    )
    elapsed_ms = (time.perf_counter() - started) * 1000
    explanations = _explain(scenario, outcomes, allocations)
    if calculate_baseline:
        explanations.append(
            f"The privacy-limited plan is {gap:.2f}% above the full-information cost benchmark."
        )

    result = OptimizationResult(
        run_id=str(uuid4()),
        scenario_name=scenario.name,
        status="optimal" if flow == total_demand else "infeasible",
        allocations=allocations,
        factory_outcomes=outcomes,
        metrics=Metrics(
            total_demand=total_demand,
            total_allocated=total_demand - total_shortage,
            total_shortage=total_shortage,
            total_network_cost=actual_total_cost,
            source_cost=round(source_cost, 2),
            production_cost=round(production_cost, 2),
            shortage_cost=round(shortage_cost, 2),
            baseline_network_cost=round(baseline_cost, 2),
            feasibility_rate=100.0 if flow == total_demand else round(flow / total_demand * 100, 2),
            optimality_gap=round(gap, 3),
            information_disclosed=disclosed,
            information_withheld=withheld,
            replanning_time_ms=round(elapsed_ms, 3),
        ),
        explanations=explanations,
        constraint_checks={},
    )
    result.constraint_checks = validate_result(scenario, result)
    return result


def _explain(
    scenario: Scenario,
    outcomes: list[FactoryOutcome],
    allocations: list[Allocation],
) -> list[str]:
    notes: list[str] = []
    alternatives = [supplier.name for supplier in scenario.suppliers if supplier.alternative]
    if alternatives and any(item.supplier_name in alternatives for item in allocations):
        notes.append(f"Alternative capacity from {', '.join(alternatives)} was activated to protect service levels.")
    for outcome in outcomes:
        factory = next(item for item in scenario.factories if item.id == outcome.factory_id)
        if outcome.shortage:
            notes.append(
                f"{factory.name} has a {outcome.shortage}-unit shortage after eligible supplier capacity was exhausted."
            )
        else:
            notes.append(f"{factory.name}'s {factory.demand}-unit requirement is fully covered before its deadline.")
    ineligible = [
        f"{supplier.name} to {factory.name}"
        for supplier in scenario.suppliers
        for factory in scenario.factories
        if supplier.lead_time_days > factory.deadline_days
    ]
    if ineligible:
        notes.append(f"Deadline constraints excluded {', '.join(ineligible)}.")
    notes.append("The coordinated plan minimizes approved sourcing, shipping, and shortage-cost signals across the network.")
    return notes


def validate_result(scenario: Scenario, result: OptimizationResult) -> dict[str, bool]:
    supplier_usage = {supplier.id: 0 for supplier in scenario.suppliers}
    factory_receipts = {factory.id: 0 for factory in scenario.factories}
    deadlines_ok = True
    for allocation in result.allocations:
        supplier_usage[allocation.supplier_id] += allocation.quantity
        factory_receipts[allocation.factory_id] += allocation.quantity
        supplier = next(item for item in scenario.suppliers if item.id == allocation.supplier_id)
        factory = next(item for item in scenario.factories if item.id == allocation.factory_id)
        deadlines_ok = deadlines_ok and supplier.lead_time_days <= factory.deadline_days
    return {
        "supplier_capacity": all(
            supplier_usage[item.id] <= item.capacity for item in scenario.suppliers
        ),
        "factory_demand": all(
            factory_receipts[item.id] <= item.demand for item in scenario.factories
        ),
        "delivery_deadlines": deadlines_ok,
        "flow_balance": all(
            factory_receipts[item.id]
            + next(outcome.shortage for outcome in result.factory_outcomes if outcome.factory_id == item.id)
            == item.demand
            for item in scenario.factories
        ),
    }
