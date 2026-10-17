from __future__ import annotations

import json
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api_schemas import DemandSpec, ScenarioCreate, SupplySpec
from backend.database.models import (
    AllocationDetail, AllocationPlan, AuditLog, DemandNode, Participant, PrivateData, Scenario, SupplyNode,
)
from backend.engine import run_benchmarks
from backend.engine.types import DemandInput, EngineScenario, SupplyInput
from backend.services.llm_explainer import LLMExplainer


APPROVED_SUPPLY_FIELDS = ["supplier_id", "component", "period", "capacity", "unit_cost", "lead_time", "minimum_order_quantity", "batch_size"]
APPROVED_DEMAND_FIELDS = ["factory_id", "component", "period", "quantity_requested", "deadline", "shortage_penalty", "priority_score"]


def seed_participants(session: Session) -> None:
    if session.scalar(select(Participant.id).limit(1)):
        return
    participants = [
        Participant(id="factory-a", name="Austin Assembly", type="FACTORY", role="Factory_A_Agent"),
        Participant(id="factory-b", name="Dallas Controls", type="FACTORY", role="Factory_B_Agent"),
        Participant(id="supplier-primary", name="Meridian Silicon", type="SUPPLIER", role="Supplier_S_Agent"),
        Participant(id="supplier-alt", name="Redwood Components", type="SUPPLIER", role="Supplier_Alt_Agent"),
    ]
    session.add_all(participants)
    session.add_all([
        PrivateData(participant_id="factory-a", field_name="unit_production_cost", field_value_encrypted_or_isolated="18.50"),
        PrivateData(participant_id="factory-a", field_name="customer_contract", field_value_encrypted_or_isolated="Atlas Mobility / confidential"),
        PrivateData(participant_id="factory-b", field_name="unit_production_cost", field_value_encrypted_or_isolated="15.75"),
        PrivateData(participant_id="factory-b", field_name="customer_contract", field_value_encrypted_or_isolated="Nova Industrial / confidential"),
        PrivateData(participant_id="supplier-primary", field_name="local_margin", field_value_encrypted_or_isolated="0.18"),
        PrivateData(participant_id="supplier-alt", field_name="local_margin", field_value_encrypted_or_isolated="0.23"),
    ])
    session.commit()


def default_specs() -> tuple[list[SupplySpec], list[DemandSpec]]:
    supplies = [
        SupplySpec(supplier_id="supplier-primary", period=1, capacity=450, unit_cost=12.25, lead_time=0, minimum_order_quantity=50, batch_size=25),
        SupplySpec(supplier_id="supplier-primary", period=2, capacity=350, unit_cost=12.75, lead_time=0, minimum_order_quantity=50, batch_size=25),
        SupplySpec(supplier_id="supplier-alt", period=1, capacity=150, unit_cost=20.50, lead_time=1, minimum_order_quantity=50, batch_size=25),
        SupplySpec(supplier_id="supplier-alt", period=2, capacity=150, unit_cost=20.00, lead_time=1, minimum_order_quantity=50, batch_size=25),
    ]
    demands = [
        DemandSpec(factory_id="factory-a", period=1, quantity_requested=350, deadline=1, shortage_penalty=42, priority_score=5),
        DemandSpec(factory_id="factory-a", period=2, quantity_requested=250, deadline=2, shortage_penalty=42, priority_score=5),
        DemandSpec(factory_id="factory-b", period=1, quantity_requested=250, deadline=2, shortage_penalty=34, priority_score=4),
        DemandSpec(factory_id="factory-b", period=2, quantity_requested=250, deadline=3, shortage_penalty=34, priority_score=4),
    ]
    return supplies, demands


def create_scenario(session: Session, payload: ScenarioCreate) -> Scenario:
    supplies, demands = default_specs()
    scenario = Scenario(
        id=payload.id or str(uuid4()), name=payload.name, status="READY",
        start_date=payload.start_date, horizon_periods=payload.horizon_periods,
    )
    session.add(scenario)
    session.flush()
    for item in payload.supplies or supplies:
        session.add(SupplyNode(scenario_id=scenario.id, **item.model_dump()))
    for item in payload.demands or demands:
        session.add(DemandNode(scenario_id=scenario.id, **item.model_dump()))
    session.commit()
    session.refresh(scenario)
    return scenario


def to_engine_scenario(session: Session, scenario: Scenario) -> EngineScenario:
    names = {item.id: item.name for item in session.scalars(select(Participant)).all()}
    return EngineScenario(
        id=scenario.id, name=scenario.name, start_date=scenario.start_date, horizon_periods=scenario.horizon_periods,
        supplies=[SupplyInput(
            id=item.id, supplier_id=item.supplier_id, supplier_name=names[item.supplier_id], component=item.component,
            period=item.period, capacity=item.capacity, unit_cost=item.unit_cost, lead_time=item.lead_time,
            minimum_order_quantity=item.minimum_order_quantity, batch_size=item.batch_size,
        ) for item in scenario.supply_nodes],
        demands=[DemandInput(
            id=item.id, factory_id=item.factory_id, factory_name=names[item.factory_id], component=item.component,
            period=item.period, quantity_requested=item.quantity_requested, deadline=item.deadline,
            shortage_penalty=item.shortage_penalty, priority_score=item.priority_score,
        ) for item in scenario.demand_nodes],
    )


def optimize_and_persist(session: Session, scenario: Scenario, accessor: str = "coordinator") -> AllocationPlan:
    engine_scenario = to_engine_scenario(session, scenario)
    private_costs = {
        item.participant_id: float(item.field_value_encrypted_or_isolated)
        for item in session.scalars(select(PrivateData).where(PrivateData.field_name == "unit_production_cost")).all()
    }
    participant_fields: dict[str, list[str]] = {}
    for item in scenario.supply_nodes:
        participant_fields[item.supplier_id] = APPROVED_SUPPLY_FIELDS
    for item in scenario.demand_nodes:
        participant_fields[item.factory_id] = APPROVED_DEMAND_FIELDS
    disclosed_count = sum(len(fields) for fields in participant_fields.values())
    report = run_benchmarks(engine_scenario, private_costs, disclosed_count)
    previous = session.scalar(select(AllocationPlan).where(AllocationPlan.scenario_id == scenario.id).order_by(AllocationPlan.timestamp.desc()))
    explainer = LLMExplainer()
    explanation, executive, participant_summaries = explainer.explain(
        report, json.loads(previous.report_json) if previous else None
    )
    report.explanation, report.executive_summary, report.participant_summaries = explanation, executive, participant_summaries
    privacy = next(item for item in report.strategies if item.strategy.startswith("Privacy-Aware"))
    plan = AllocationPlan(
        id=str(uuid4()), scenario_id=scenario.id, total_network_cost=privacy.total_network_cost,
        optimality_gap=privacy.optimality_gap, strategy=privacy.strategy,
        report_json=report.model_dump_json(),
    )
    session.add(plan)
    session.flush()
    for item in privacy.allocations:
        session.add(AllocationDetail(
            plan_id=plan.id, factory_id=item.factory_id, supplier_id=item.supplier_id,
            component=item.component, allocated_quantity=item.quantity, ship_period=item.ship_period,
            delivery_date=scenario.start_date + timedelta(days=item.delivery_period - 1),
        ))
    for participant_id, fields in participant_fields.items():
        session.add(AuditLog(
            plan_id=plan.id, accessor_participant_id=accessor, target_participant_id=participant_id,
            fields_disclosed=json.dumps(fields), action="OPTIMIZATION_DISCLOSURE",
        ))
    scenario.status = "OPTIMIZED"
    session.commit()
    session.refresh(plan)
    return plan
