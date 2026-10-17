from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.audit import AuditStore
from app.coordination import CoordinationService
from app.models import (
    DisruptionRequest,
    OptimizationRequest,
    OptimizationResult,
    Scenario,
)
from app.security import AccessDenied, filter_participant_record


ROOT = Path(__file__).resolve().parents[1]


def load_sample_scenario() -> Scenario:
    return Scenario.model_validate_json((ROOT / "data" / "sample_scenario.json").read_text(encoding="utf-8"))


def create_app(database: str | Path | None = None) -> FastAPI:
    app = FastAPI(
        title="TradeOff API",
        version="1.0.0",
        description="Privacy-aware supply-chain coordination and disruption replanning.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:8501", "http://127.0.0.1:8501"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    store = AuditStore(database or os.getenv("TRADEOFF_DB", str(ROOT / "tradeoff.db")))
    app.state.coordinator = CoordinationService(load_sample_scenario(), store)
    app.state.audit_store = store

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "tradeoff"}

    @app.get("/scenario", response_model=Scenario)
    async def get_scenario() -> Scenario:
        return app.state.coordinator.scenario

    @app.get("/coordination/messages")
    async def get_coordination_messages() -> list[dict[str, object]]:
        return [item.model_dump() for item in app.state.coordinator.approved_messages()]

    @app.post("/optimize", response_model=OptimizationResult)
    async def optimize(request: OptimizationRequest) -> OptimizationResult:
        return app.state.coordinator.optimize(request.scenario)

    @app.post("/disrupt", response_model=OptimizationResult)
    async def disrupt(request: DisruptionRequest) -> OptimizationResult:
        try:
            return app.state.coordinator.replan(
                request.supplier_id, request.new_capacity, request.demand_changes
            )
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.get("/participants/{participant_id}")
    async def participant(
        participant_id: str,
        x_participant_id: str = Header(default="anonymous"),
        x_role: str = Header(default="auditor"),
    ) -> dict[str, object]:
        scenario = app.state.coordinator.scenario
        record = next(
            (
                item
                for item in [*scenario.factories, *scenario.suppliers]
                if item.id == participant_id
            ),
            None,
        )
        if record is None:
            raise HTTPException(status_code=404, detail="Participant not found")
        try:
            return filter_participant_record(record, x_participant_id, x_role)
        except AccessDenied as error:
            raise HTTPException(status_code=403, detail=str(error)) from error

    @app.get("/audit")
    async def audit(
        limit: int = Query(default=50, ge=1, le=500),
        x_role: str = Header(default="auditor"),
    ) -> list[dict[str, object]]:
        if x_role not in {"admin", "auditor"}:
            raise HTTPException(status_code=403, detail="Audit access requires auditor or admin role")
        return app.state.audit_store.list_events(limit)

    @app.post("/reset", response_model=Scenario)
    async def reset(x_role: str = Header(default="admin")) -> Scenario:
        if x_role != "admin":
            raise HTTPException(status_code=403, detail="Admin role required")
        app.state.coordinator.scenario = load_sample_scenario()
        app.state.audit_store.record("scenario_reset", "admin", {"source": "sample"})
        return app.state.coordinator.scenario

    return app


app = create_app()
