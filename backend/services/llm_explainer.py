from __future__ import annotations

import os
import re
from typing import Any

from pydantic import BaseModel, Field

from backend.engine.types import BenchmarkReport


class ParsedDisruption(BaseModel):
    supplier_id: str
    capacity_loss_percent: float = Field(ge=0, le=100)
    period: int = Field(ge=1)


class LLMExplainer:
    """Reporting-only LLM adapter. Solver outputs are immutable inputs to this layer."""

    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.model = os.getenv("OPENAI_MODEL", "gpt-6-astra")

    @property
    def enabled(self) -> bool:
        return bool(self.api_key) and os.getenv("TRADEOFF_ENABLE_LLM", "0") == "1"

    def parse_disruption(self, text: str) -> ParsedDisruption:
        if self.enabled:
            from openai import OpenAI

            response = OpenAI(api_key=self.api_key).responses.parse(
                model=self.model,
                input=[
                    {"role": "system", "content": "Extract a supply disruption only. Never calculate allocations."},
                    {"role": "user", "content": text},
                ],
                text_format=ParsedDisruption,
            )
            if response.output_parsed:
                return response.output_parsed
        percent = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
        day = re.search(r"(?:day|period)\s*(\d+)", text, re.IGNORECASE)
        supplier = "supplier-primary" if "primary" in text.lower() else "supplier-alt"
        return ParsedDisruption(
            supplier_id=supplier,
            capacity_loss_percent=float(percent.group(1)) if percent else 40.0,
            period=int(day.group(1)) if day else 2,
        )

    def explain(self, report: BenchmarkReport, previous_report: dict[str, Any] | None = None) -> tuple[str, str, dict[str, str]]:
        # Deterministic outputs keep the demo operational without an API key.
        if not self.enabled:
            explanation = report.explanation
            if previous_report:
                previous = next(
                    item for item in previous_report["strategies"]
                    if item["strategy"].startswith("Privacy-Aware")
                )
                current = next(
                    item for item in report.strategies
                    if item.strategy.startswith("Privacy-Aware")
                )
                cost_delta = current.total_network_cost - previous["total_network_cost"]
                shortage_delta = current.unmet_demand - previous["unmet_demand"]
                explanation = (
                    f"After the disruption, authoritative OR-Tools allocations changed network cost by "
                    f"${cost_delta:,.0f} and unmet demand by {shortage_delta:+,} units. " + report.explanation
                )
            return explanation, report.executive_summary, report.participant_summaries
        from openai import OpenAI

        class Narrative(BaseModel):
            allocation_delta_explanation: str
            disruption_impact_summary: str
            participant_summaries: dict[str, str]

        response = OpenAI(api_key=self.api_key).responses.parse(
            model=self.model,
            input=[
                {"role": "system", "content": (
                    "Explain supplied authoritative OR-Tools results. Never recompute, alter, infer hidden competitor data, "
                    "or recommend allocations. Participant summaries must mention only that participant's results."
                )},
                {"role": "user", "content": f"Previous={previous_report}; Current={report.model_dump(mode='json')}"},
            ],
            text_format=Narrative,
        )
        parsed = response.output_parsed
        if parsed is None:
            return report.explanation, report.executive_summary, report.participant_summaries
        return parsed.allocation_delta_explanation, parsed.disruption_impact_summary, parsed.participant_summaries
