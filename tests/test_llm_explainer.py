from backend.services.llm_explainer import LLMExplainer


def test_deterministic_parser_does_not_require_llm(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    parsed = LLMExplainer().parse_disruption(
        "Simulate primary supplier losing 50% capacity on day 2"
    )
    assert parsed.supplier_id == "supplier-primary"
    assert parsed.capacity_loss_percent == 50
    assert parsed.period == 2
