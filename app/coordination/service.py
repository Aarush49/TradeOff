from __future__ import annotations

from copy import deepcopy

from app.agents import FactoryAgent, SupplierAgent
from app.audit.store import AuditStore
from app.models import CoordinationMessage, OptimizationResult, Scenario
from app.optimizer import optimize_scenario


class CoordinationService:
    def __init__(self, scenario: Scenario, audit_store: AuditStore) -> None:
        self.scenario = scenario
        self.audit_store = audit_store
        self.last_result: OptimizationResult | None = None

    def approved_messages(self) -> list[CoordinationMessage]:
        messages = [FactoryAgent(item).request() for item in self.scenario.factories]
        messages.extend(SupplierAgent(item).offer() for item in self.scenario.suppliers)
        return messages

    def optimize(self, scenario: Scenario | None = None, event: str = "optimization") -> OptimizationResult:
        active_scenario = scenario or self.scenario
        result = optimize_scenario(active_scenario)
        self.scenario = active_scenario
        self.last_result = result
        self.audit_store.record(event, "coordinator", result.model_dump(mode="json"))
        return result

    def replan(
        self,
        supplier_id: str,
        new_capacity: int,
        demand_changes: dict[str, int],
    ) -> OptimizationResult:
        updated = deepcopy(self.scenario)
        supplier = next((item for item in updated.suppliers if item.id == supplier_id), None)
        if supplier is None:
            raise KeyError(f"Unknown supplier: {supplier_id}")
        supplier.capacity = new_capacity
        for factory_id, demand in demand_changes.items():
            factory = next((item for item in updated.factories if item.id == factory_id), None)
            if factory is None:
                raise KeyError(f"Unknown factory: {factory_id}")
            if demand < 0:
                raise ValueError("Demand cannot be negative")
            factory.demand = demand
        return self.optimize(updated, event="disruption_replan")
