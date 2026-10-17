from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from backend.engine.types import BenchmarkReport


class ParticipantProfile(BaseModel):
    id: str
    name: str
    type: str
    role: str


class PrivateField(BaseModel):
    field_name: str
    field_value_encrypted_or_isolated: str


class SupplySpec(BaseModel):
    supplier_id: str
    component: str = "MCU"
    period: int = Field(ge=1)
    capacity: int = Field(ge=0)
    unit_cost: float = Field(ge=0)
    lead_time: int = Field(ge=0)
    minimum_order_quantity: int = Field(default=0, ge=0)
    batch_size: int = Field(default=25, ge=1)


class DemandSpec(BaseModel):
    factory_id: str
    component: str = "MCU"
    period: int = Field(ge=1)
    quantity_requested: int = Field(ge=0)
    deadline: int = Field(ge=1)
    shortage_penalty: float = Field(gt=0)
    priority_score: int = Field(default=3, ge=1, le=5)


class ScenarioCreate(BaseModel):
    id: str | None = None
    name: str = "Semiconductor recovery — North America"
    start_date: date = date(2026, 10, 17)
    horizon_periods: int = Field(default=3, ge=1, le=30)
    supplies: list[SupplySpec] | None = None
    demands: list[DemandSpec] | None = None


class ScenarioRead(BaseModel):
    id: str
    name: str
    status: str
    start_date: date
    horizon_periods: int
    supplies: list[SupplySpec]
    demands: list[DemandSpec]


class OptimizeRequest(BaseModel):
    scenario_id: str


class DisruptionRequest(BaseModel):
    scenario_id: str
    preset: str | None = "PRIMARY_CAPACITY_LOSS_40"
    supplier_id: str | None = None
    capacity_loss_percent: float | None = Field(default=None, ge=0, le=100)
    period: int | None = Field(default=None, ge=1)
    natural_language: str | None = None


class OptimizeResponse(BaseModel):
    plan_id: str
    report: BenchmarkReport
    llm_used: bool


class AuditRead(BaseModel):
    id: int
    plan_id: str | None
    accessor_participant_id: str
    target_participant_id: str
    fields_disclosed: list[str]
    action: str
    timestamp: datetime
