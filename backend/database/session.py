from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base


def create_session_factory(database_url: str | None = None) -> sessionmaker[Session]:
    if database_url is None:
        path = Path(__file__).resolve().parents[2] / "tradeoff.db"
        database_url = f"sqlite:///{path.as_posix()}"
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    engine = create_engine(database_url, connect_args=connect_args)
    return sessionmaker(bind=engine, expire_on_commit=False)


def init_database(factory: sessionmaker[Session]) -> None:
    Base.metadata.create_all(factory.kw["bind"])
