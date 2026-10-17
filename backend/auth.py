from __future__ import annotations

import os
from dataclasses import dataclass

from fastapi import Header, HTTPException


@dataclass(frozen=True)
class Principal:
    participant_id: str
    role: str


DEMO_KEYS = {
    os.getenv("TRADEOFF_COORDINATOR_KEY", "coordinator-demo-key"): Principal("coordinator", "COORDINATOR"),
    os.getenv("TRADEOFF_AUDITOR_KEY", "auditor-demo-key"): Principal("auditor", "AUDITOR"),
    os.getenv("FACTORY_A_AGENT_KEY", "factory-a-demo-key"): Principal("factory-a", "FACTORY_AGENT"),
    os.getenv("FACTORY_B_AGENT_KEY", "factory-b-demo-key"): Principal("factory-b", "FACTORY_AGENT"),
    os.getenv("SUPPLIER_PRIMARY_AGENT_KEY", "supplier-primary-demo-key"): Principal("supplier-primary", "SUPPLIER_AGENT"),
    os.getenv("SUPPLIER_ALT_AGENT_KEY", "supplier-alt-demo-key"): Principal("supplier-alt", "SUPPLIER_AGENT"),
}


def get_principal(x_api_key: str = Header(default="", alias="X-API-Key")) -> Principal:
    principal = DEMO_KEYS.get(x_api_key)
    if principal is None:
        raise HTTPException(status_code=401, detail="A valid X-API-Key is required")
    return principal


def require_coordinator(principal: Principal) -> None:
    if principal.role != "COORDINATOR":
        raise HTTPException(status_code=403, detail="Coordinator access required")
