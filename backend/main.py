from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from typing import Iterator

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api_schemas import (
    AuditRead, DisruptionRequest, OptimizeRequest, OptimizeResponse, ParticipantProfile,
    PrivateField, ScenarioCreate, ScenarioRead,
)
from backend.auth import Principal, get_principal, require_coordinator
from backend.database import create_session_factory, init_database
from backend.database.models import AllocationPlan, AuditLog, Participant, PrivateData, Scenario, SupplyNode
from backend.engine.types import BenchmarkReport
from backend.services.llm_explainer import LLMExplainer
from backend.services.scenarios import create_scenario, optimize_and_persist, seed_participants


def create_app(database_url: str | None = None) -> FastAPI:
    factory = create_session_factory(database_url or os.getenv("TRADEOFF_DATABASE_URL"))
    init_database(factory)
    with factory() as session:
        seed_participants(session)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield

    app = FastAPI(title="TradeOff Coordination API", version="2.0.0", lifespan=lifespan)
    app.state.session_factory = factory
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:8501", "http://127.0.0.1:8501"],
        allow_methods=["*"], allow_headers=["*"],
    )

    def db() -> Iterator[Session]:
        with factory() as session:
            yield session

    def scenario_read(item: Scenario) -> ScenarioRead:
        return ScenarioRead(
            id=item.id, name=item.name, status=item.status, start_date=item.start_date,
            horizon_periods=item.horizon_periods,
            supplies=[{
                "supplier_id": row.supplier_id, "component": row.component, "period": row.period,
                "capacity": row.capacity, "unit_cost": row.unit_cost, "lead_time": row.lead_time,
                "minimum_order_quantity": row.minimum_order_quantity, "batch_size": row.batch_size,
            } for row in item.supply_nodes],
            demands=[{
                "factory_id": row.factory_id, "component": row.component, "period": row.period,
                "quantity_requested": row.quantity_requested, "deadline": row.deadline,
                "shortage_penalty": row.shortage_penalty, "priority_score": row.priority_score,
            } for row in item.demand_nodes],
        )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "optimizer": "OR-Tools CP-SAT", "database": "SQLAlchemy/SQLite"}

    @app.post("/scenarios", response_model=ScenarioRead, status_code=201)
    def scenarios_create(
        payload: ScenarioCreate,
        principal: Principal = Depends(get_principal), session: Session = Depends(db),
    ) -> ScenarioRead:
        require_coordinator(principal)
        if payload.id:
            existing = session.get(Scenario, payload.id)
            if existing:
                return scenario_read(existing)
        return scenario_read(create_scenario(session, payload))

    @app.get("/scenarios/{scenario_id}", response_model=ScenarioRead)
    def scenarios_get(
        scenario_id: str, _: Principal = Depends(get_principal), session: Session = Depends(db),
    ) -> ScenarioRead:
        item = session.get(Scenario, scenario_id)
        if not item:
            raise HTTPException(404, "Scenario not found")
        return scenario_read(item)

    @app.get("/participants", response_model=list[ParticipantProfile])
    def participants(
        _: Principal = Depends(get_principal), session: Session = Depends(db),
    ) -> list[ParticipantProfile]:
        return [ParticipantProfile.model_validate(item, from_attributes=True) for item in session.scalars(select(Participant)).all()]

    @app.get("/participants/{participant_id}/private-data", response_model=list[PrivateField])
    def private_data(
        participant_id: str, principal: Principal = Depends(get_principal), session: Session = Depends(db),
    ) -> list[PrivateField]:
        if principal.participant_id != participant_id and principal.role != "COORDINATOR":
            session.add(AuditLog(
                plan_id=None, accessor_participant_id=principal.participant_id,
                target_participant_id=participant_id, fields_disclosed="[]", action="PRIVATE_ACCESS_DENIED",
            ))
            session.commit()
            raise HTTPException(403, "Participants may only access their own private data")
        rows = session.scalars(select(PrivateData).where(PrivateData.participant_id == participant_id)).all()
        session.add(AuditLog(
            plan_id=None, accessor_participant_id=principal.participant_id,
            target_participant_id=participant_id,
            fields_disclosed=json.dumps([item.field_name for item in rows]), action="PRIVATE_ACCESS_GRANTED",
        ))
        session.commit()
        return [PrivateField.model_validate(item, from_attributes=True) for item in rows]

    @app.post("/optimize", response_model=OptimizeResponse)
    def optimize(
        payload: OptimizeRequest,
        principal: Principal = Depends(get_principal), session: Session = Depends(db),
    ) -> OptimizeResponse:
        require_coordinator(principal)
        scenario = session.get(Scenario, payload.scenario_id)
        if not scenario:
            raise HTTPException(404, "Scenario not found")
        plan = optimize_and_persist(session, scenario, principal.participant_id)
        return OptimizeResponse(
            plan_id=plan.id, report=BenchmarkReport.model_validate_json(plan.report_json),
            llm_used=LLMExplainer().enabled,
        )

    @app.post("/disrupt", response_model=OptimizeResponse)
    def disrupt(
        payload: DisruptionRequest,
        principal: Principal = Depends(get_principal), session: Session = Depends(db),
    ) -> OptimizeResponse:
        require_coordinator(principal)
        scenario = session.get(Scenario, payload.scenario_id)
        if not scenario:
            raise HTTPException(404, "Scenario not found")
        supplier_id, loss, period = payload.supplier_id, payload.capacity_loss_percent, payload.period
        if payload.natural_language:
            parsed = LLMExplainer().parse_disruption(payload.natural_language)
            supplier_id, loss, period = parsed.supplier_id, parsed.capacity_loss_percent, parsed.period
        if payload.preset == "PRIMARY_CAPACITY_LOSS_40" and not payload.natural_language:
            supplier_id, loss, period = "supplier-primary", 40.0, 2
        if supplier_id is None or loss is None or period is None:
            raise HTTPException(422, "Disruption requires supplier, capacity loss percent, and period")
        nodes = session.scalars(select(SupplyNode).where(
            SupplyNode.scenario_id == scenario.id,
            SupplyNode.supplier_id == supplier_id,
            SupplyNode.period == period,
        )).all()
        if not nodes:
            raise HTTPException(404, "Matching supply node not found")
        for node in nodes:
            node.capacity = int(node.capacity * (1 - loss / 100))
        scenario.status = "DISRUPTED"
        session.add(AuditLog(
            plan_id=None, accessor_participant_id=principal.participant_id,
            target_participant_id=supplier_id,
            fields_disclosed=json.dumps(["capacity", "period"]), action="DISRUPTION_APPLIED",
        ))
        session.commit()
        plan = optimize_and_persist(session, scenario, principal.participant_id)
        return OptimizeResponse(
            plan_id=plan.id, report=BenchmarkReport.model_validate_json(plan.report_json),
            llm_used=LLMExplainer().enabled,
        )

    @app.get("/audit-log", response_model=list[AuditRead])
    def audit_log(
        principal: Principal = Depends(get_principal), session: Session = Depends(db),
    ) -> list[AuditRead]:
        if principal.role not in {"COORDINATOR", "AUDITOR"}:
            raise HTTPException(403, "Audit access requires coordinator or auditor role")
        rows = session.scalars(select(AuditLog).order_by(AuditLog.id.desc())).all()
        return [AuditRead(
            id=item.id, plan_id=item.plan_id, accessor_participant_id=item.accessor_participant_id,
            target_participant_id=item.target_participant_id,
            fields_disclosed=json.loads(item.fields_disclosed), action=item.action, timestamp=item.timestamp,
        ) for item in rows]

    @app.get("/plans/{plan_id}/participant-summary")
    def participant_summary(
        plan_id: str, principal: Principal = Depends(get_principal), session: Session = Depends(db),
    ) -> dict[str, str]:
        plan = session.get(AllocationPlan, plan_id)
        if not plan:
            raise HTTPException(404, "Plan not found")
        if principal.role not in {"FACTORY_AGENT", "COORDINATOR"}:
            raise HTTPException(403, "Participant plan summary requires factory or coordinator access")
        summaries = BenchmarkReport.model_validate_json(plan.report_json).participant_summaries
        if principal.role == "COORDINATOR":
            return summaries
        if principal.participant_id not in summaries:
            raise HTTPException(403, "No summary is available for this participant")
        return {principal.participant_id: summaries[principal.participant_id]}

    return app


app = create_app()
