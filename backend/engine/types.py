from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class SupplyInput(BaseModel):
    id: int
    supplier_id: str
    supplier_name: str
    component: str
    period: int
    capacity: int
    unit_cost: float
    lead_time: int
    minimum_order_quantity: int
    batch_size: int


class DemandInput(BaseModel):
    id: int
    factory_id: str
    factory_name: str
    component: str
    period: int
    quantity_requested: int
    deadline: int
    shortage_penalty: float
    priority_score: int


class EngineScenario(BaseModel):
    id: str
    name: str
    start_date: date
    horizon_periods: int
    supplies: list[SupplyInput]
    demands: list[DemandInput]


class Allocation(BaseModel):
    supplier_id: str
    supplier_name: str
    factory_id: str
    factory_name: str
    component: str
    quantity: int
    ship_period: int
    delivery_period: int
    unit_cost: float


class StrategyMetrics(BaseModel):
    strategy: str
    status: str
    total_network_cost: float
    unmet_demand: int
    optimality_gap: float = 0
    disclosed_fields: int = 0
    solve_time_ms: float
    allocations: list[Allocation] = Field(default_factory=list)
    shortages: dict[str, int] = Field(default_factory=dict)


class BenchmarkReport(BaseModel):
    scenario_id: str
    recommended_strategy: str = "Privacy-Aware TradeOff Coordination"
    strategies: list[StrategyMetrics]
    explanation: str
    executive_summary: str
    participant_summaries: dict[str, str]
