"""Declarative base and shared metadata."""

from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

from app.db.naming import NAMING_CONVENTION


class Base(DeclarativeBase):
    """Base class for all Sthalo ORM models."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
