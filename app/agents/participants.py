from __future__ import annotations

from app.models import CoordinationMessage, Factory, Supplier


class FactoryAgent:
    """Keeps private factory fields local and emits only approved coordination data."""

    def __init__(self, factory: Factory) -> None:
        self.factory = factory

    def request(self) -> CoordinationMessage:
        return CoordinationMessage(
            sender_id=self.factory.id,
            kind="demand_request",
            approved_payload={
                "factory_id": self.factory.id,
                "demand": self.factory.demand,
                "deadline_days": self.factory.deadline_days,
                "priority": self.factory.priority,
                "shortage_penalty": self.factory.shortage_penalty,
            },
        )

    def validate(self, allocated: int) -> bool:
        return 0 <= allocated <= self.factory.demand


class SupplierAgent:
    """Publishes a bounded offer without exposing reliability or internal records."""

    def __init__(self, supplier: Supplier) -> None:
        self.supplier = supplier

    def offer(self) -> CoordinationMessage:
        return CoordinationMessage(
            sender_id=self.supplier.id,
            kind="supply_offer",
            approved_payload={
                "supplier_id": self.supplier.id,
                "capacity": self.supplier.capacity,
                "unit_cost": self.supplier.unit_cost,
                "lead_time_days": self.supplier.lead_time_days,
                "alternative": self.supplier.alternative,
            },
        )
