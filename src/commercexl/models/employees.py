from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from commercexl.models.orm_base import CommerceBase


class ClientORM(CommerceBase):
    __tablename__ = "commerce_client"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    about_me: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(25), nullable=False, index=True, default="new")


class EmployeeORM(CommerceBase):
    __tablename__ = "commerce_employee"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    document: Mapped[str | None] = mapped_column(String(100))
    legal_type: Mapped[str | None] = mapped_column(String(50))
    bank_bik: Mapped[str | None] = mapped_column(String(150))
    bank_name: Mapped[str | None] = mapped_column(String(250))
    corr_account: Mapped[str | None] = mapped_column(String(250))
    balance_account: Mapped[str | None] = mapped_column(String(250))
    address: Mapped[str | None] = mapped_column(String(250))
    legal_address: Mapped[str | None] = mapped_column(String(250))
    inn: Mapped[str | None] = mapped_column(String(250))
    ogrn: Mapped[str | None] = mapped_column(String(250))
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True, default="working")
    education: Mapped[str | None] = mapped_column(Text)
    about_me: Mapped[str | None] = mapped_column(Text)
    experience_text: Mapped[str | None] = mapped_column(Text)
    is_employed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    experience_start: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    auto_schedule_renewal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    kind: Mapped[str] = mapped_column(String(100), nullable=False, index=True)


class EmployeeAvailabilityIntervalORM(CommerceBase):
    __tablename__ = "commerce_employeeavailabilityinterval"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


class EmployeeLeaveORM(CommerceBase):
    __tablename__ = "commerce_employeeleave"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    leave_type: Mapped[str] = mapped_column(String(20), nullable=False)
    start: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    end: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    reason: Mapped[str | None] = mapped_column(Text)


