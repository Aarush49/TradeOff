from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Factory(BaseModel):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]+$")
    name: str
    demand: int = Field(ge=0)
    shortage_penalty: float = Field(gt=0)
    priority: int = Field(default=3, ge=1, le=5)
    deadline_days: int = Field(default=7, ge=1)
    production_cost: float = Field(default=0, ge=0)
    customer: str = "Private customer"


class Supplier(BaseModel):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]+$")
    name: str
    capacity: int = Field(ge=0)
    unit_cost: float = Field(ge=0)
    lead_time_days: int = Field(default=3, ge=1)
    alternative: bool = False
    reliability: float = Field(default=0.95, ge=0, le=1)


class Scenario(BaseModel):
    name: str = "Coordination scenario"
    factories: list[Factory]
    suppliers: list[Supplier]
    shipping_costs: dict[str, dict[str, float]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def unique_ids(self) -> "Scenario":
        factory_ids = [item.id for item in self.factories]
        supplier_ids = [item.id for item in self.suppliers]
        if len(factory_ids) != len(set(factory_ids)):
            raise ValueError("Factory IDs must be unique")
        if len(supplier_ids) != len(set(supplier_ids)):
            raise ValueError("Supplier IDs must be unique")
        return self


class Allocation(BaseModel):
    supplier_id: str
    supplier_name: str
    factory_id: str
    factory_name: str
    quantity: int
    unit_cost: float
    total_cost: float


class FactoryOutcome(BaseModel):
    factory_id: str
    demand: int
    allocated: int
    shortage: int
    service_level: float


class Metrics(BaseModel):
    total_demand: int
    total_allocated: int
    total_shortage: int
    total_network_cost: float
    source_cost: float
    production_cost: float
    shortage_cost: float
    baseline_network_cost: float
    feasibility_rate: float
    optimality_gap: float
    information_disclosed: int
    information_withheld: int
    replanning_time_ms: float


class OptimizationResult(BaseModel):
    run_id: str
    scenario_name: str
    status: Literal["optimal", "infeasible"]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    allocations: list[Allocation]
    factory_outcomes: list[FactoryOutcome]
    metrics: Metrics
    explanations: list[str]
    constraint_checks: dict[str, bool]


class DisruptionRequest(BaseModel):
    supplier_id: str
    new_capacity: int = Field(ge=0)
    demand_changes: dict[str, int] = Field(default_factory=dict)


class OptimizationRequest(BaseModel):
    scenario: Scenario | None = None


class CoordinationMessage(BaseModel):
    sender_id: str
    kind: Literal["demand_request", "supply_offer", "feasibility", "allocation"]
    approved_payload: dict[str, str | int | float | bool]
