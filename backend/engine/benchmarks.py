from __future__ import annotations

from .solver import solve_greedy, solve_optimal
from .types import BenchmarkReport, EngineScenario


def run_benchmarks(
    scenario: EngineScenario,
    private_production_costs: dict[str, float],
    disclosed_fields: int,
) -> BenchmarkReport:
    full = solve_optimal(
        scenario,
        strategy="Full Information Optimum",
        private_production_costs=private_production_costs,
        disclosed_fields=disclosed_fields + len(private_production_costs),
    )
    privacy = solve_optimal(
        scenario,
        strategy="Privacy-Aware TradeOff Coordination",
        private_production_costs={},
        disclosed_fields=disclosed_fields,
    )
    # Evaluate the privacy-aware allocation with actual private production cost after solving.
    privacy.total_network_cost += round(sum(
        allocation.quantity * private_production_costs.get(allocation.factory_id, 0)
        for allocation in privacy.allocations
    ), 2)
    fcfs = solve_greedy(
        scenario, strategy="First-Come, First-Served (FCFS)", by_priority=False,
        private_production_costs=private_production_costs,
    )
    priority = solve_greedy(
        scenario, strategy="Priority-Only Allocation", by_priority=True,
        private_production_costs=private_production_costs,
    )
    for result in (full, privacy, fcfs, priority):
        result.optimality_gap = round(
            ((result.total_network_cost - full.total_network_cost) / full.total_network_cost * 100)
            if full.total_network_cost else 0,
            3,
        )
    summaries: dict[str, str] = {}
    for demand in scenario.demands:
        received = sum(item.quantity for item in privacy.allocations if item.factory_id == demand.factory_id)
        summaries[demand.factory_id] = (
            f"Your site is allocated {received:,} units across the planning horizon; "
            f"competitor costs and contract terms remain undisclosed."
        )
    explanation = (
        f"TradeOff selected {sum(item.quantity for item in privacy.allocations):,} units while honoring "
        "inventory, batch, MOQ, and hard lead-time constraints. Allocation quantities were computed only by OR-Tools."
    )
    executive = (
        f"The privacy-aware plan costs ${privacy.total_network_cost:,.0f}, a {privacy.optimality_gap:.2f}% gap "
        f"to the full-information optimum, with {privacy.unmet_demand:,} units unmet."
    )
    return BenchmarkReport(
        scenario_id=scenario.id,
        strategies=[full, privacy, fcfs, priority],
        explanation=explanation,
        executive_summary=executive,
        participant_summaries=summaries,
    )
