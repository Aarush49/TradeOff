from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class ParticipantType(str, Enum):
    FACTORY = "FACTORY"
    SUPPLIER = "SUPPLIER"


class Participant(Base):
    __tablename__ = "participants"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    role: Mapped[str] = mapped_column(String(64), nullable=False)
    private_data: Mapped[list["PrivateData"]] = relationship(cascade="all, delete-orphan")


class PrivateData(Base):
    __tablename__ = "private_data"
    id: Mapped[int] = mapped_column(primary_key=True)
    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.id"), index=True)
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    field_value_encrypted_or_isolated: Mapped[str] = mapped_column(Text, nullable=False)


class Scenario(Base):
    __tablename__ = "scenarios"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="READY")
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    horizon_periods: Mapped[int] = mapped_column(Integer, default=3)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    supply_nodes: Mapped[list["SupplyNode"]] = relationship(cascade="all, delete-orphan")
    demand_nodes: Mapped[list["DemandNode"]] = relationship(cascade="all, delete-orphan")


class SupplyNode(Base):
    __tablename__ = "supply_nodes"
    id: Mapped[int] = mapped_column(primary_key=True)
    scenario_id: Mapped[str] = mapped_column(ForeignKey("scenarios.id"), index=True)
    supplier_id: Mapped[str] = mapped_column(ForeignKey("participants.id"), index=True)
    component: Mapped[str] = mapped_column(String(80), nullable=False)
    period: Mapped[int] = mapped_column(Integer, nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_cost: Mapped[float] = mapped_column(Float, nullable=False)
    lead_time: Mapped[int] = mapped_column(Integer, default=0)
    minimum_order_quantity: Mapped[int] = mapped_column(Integer, default=0)
    batch_size: Mapped[int] = mapped_column(Integer, default=1)


class DemandNode(Base):
    __tablename__ = "demand_nodes"
    id: Mapped[int] = mapped_column(primary_key=True)
    scenario_id: Mapped[str] = mapped_column(ForeignKey("scenarios.id"), index=True)
    factory_id: Mapped[str] = mapped_column(ForeignKey("participants.id"), index=True)
    component: Mapped[str] = mapped_column(String(80), nullable=False)
    period: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_requested: Mapped[int] = mapped_column(Integer, nullable=False)
    deadline: Mapped[int] = mapped_column(Integer, nullable=False)
    shortage_penalty: Mapped[float] = mapped_column(Float, nullable=False)
    priority_score: Mapped[int] = mapped_column(Integer, default=3)


class AllocationPlan(Base):
    __tablename__ = "allocation_plans"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    scenario_id: Mapped[str] = mapped_column(ForeignKey("scenarios.id"), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    total_network_cost: Mapped[float] = mapped_column(Float, nullable=False)
    optimality_gap: Mapped[float] = mapped_column(Float, default=0)
    strategy: Mapped[str] = mapped_column(String(80), nullable=False)
    report_json: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[list["AllocationDetail"]] = relationship(cascade="all, delete-orphan")


class AllocationDetail(Base):
    __tablename__ = "allocation_details"
    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[str] = mapped_column(ForeignKey("allocation_plans.id"), index=True)
    factory_id: Mapped[str] = mapped_column(ForeignKey("participants.id"))
    supplier_id: Mapped[str] = mapped_column(ForeignKey("participants.id"))
    component: Mapped[str] = mapped_column(String(80), nullable=False)
    allocated_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    ship_period: Mapped[int] = mapped_column(Integer, nullable=False)
    delivery_date: Mapped[date] = mapped_column(Date, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[str | None] = mapped_column(ForeignKey("allocation_plans.id"), nullable=True, index=True)
    accessor_participant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    target_participant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    fields_disclosed: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(String(80), default="DISCLOSURE")
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
