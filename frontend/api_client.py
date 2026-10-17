from __future__ import annotations

import os
from typing import Any

import requests


class TradeOffAPI:
    def __init__(self) -> None:
        self.base_url = os.getenv("TRADEOFF_API_URL", "http://127.0.0.1:8000").rstrip("/")
        self.headers = {"X-API-Key": os.getenv("TRADEOFF_API_KEY", "coordinator-demo-key")}

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        response = requests.request(method, f"{self.base_url}{path}", headers=self.headers, timeout=30, **kwargs)
        response.raise_for_status()
        return response.json()

    def health(self) -> dict[str, str]:
        return self._request("GET", "/health")

    def create_scenario(self) -> dict[str, Any]:
        return self._request("POST", "/scenarios", json={})

    def get_scenario(self, scenario_id: str) -> dict[str, Any]:
        return self._request("GET", f"/scenarios/{scenario_id}")

    def optimize(self, scenario_id: str) -> dict[str, Any]:
        return self._request("POST", "/optimize", json={"scenario_id": scenario_id})

    def disrupt(self, scenario_id: str, natural_language: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"scenario_id": scenario_id, "preset": "PRIMARY_CAPACITY_LOSS_40"}
        if natural_language:
            payload["natural_language"] = natural_language
            payload["preset"] = None
        return self._request("POST", "/disrupt", json=payload)

    def audit_log(self) -> list[dict[str, Any]]:
        return self._request("GET", "/audit-log")
