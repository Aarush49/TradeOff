import pytest

from app.models import Factory
from app.security import AccessDenied, filter_participant_record


FACTORY = Factory(
    id="factory-a",
    name="Factory A",
    demand=600,
    shortage_penalty=42,
    production_cost=18.5,
    customer="Private Co",
)


def test_owner_can_see_private_record() -> None:
    record = filter_participant_record(FACTORY, "factory-a", "factory")
    assert record["production_cost"] == 18.5
    assert record["customer"] == "Private Co"


def test_other_participant_only_sees_approved_fields() -> None:
    record = filter_participant_record(FACTORY, "factory-b", "factory")
    assert "demand" in record
    assert "production_cost" not in record
    assert "customer" not in record


def test_unknown_role_is_denied() -> None:
    with pytest.raises(AccessDenied):
        filter_participant_record(FACTORY, "outsider", "guest")
