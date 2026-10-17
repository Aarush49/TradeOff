from __future__ import annotations

from app.models import Factory, Supplier


class AccessDenied(PermissionError):
    pass


def filter_participant_record(
    record: Factory | Supplier,
    requester_id: str,
    role: str,
) -> dict[str, object]:
    data = record.model_dump()
    if role == "admin" or requester_id == record.id:
        return data
    if role not in {"factory", "supplier", "auditor"}:
        raise AccessDenied("A recognized participant role is required")
    if isinstance(record, Factory):
        return {
            "id": record.id,
            "name": record.name,
            "demand": record.demand,
            "deadline_days": record.deadline_days,
            "priority": record.priority,
        }
    return {
        "id": record.id,
        "name": record.name,
        "capacity": record.capacity,
        "lead_time_days": record.lead_time_days,
        "alternative": record.alternative,
    }
