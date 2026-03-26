from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

from commercexl.models.naming import NAMING_CONVENTION


class CommerceBase(DeclarativeBase):
    """Standalone `DeclarativeBase` for core `commercexl` models."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


__all__ = ("CommerceBase",)
