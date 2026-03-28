from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from commercexl.models.orm_base import CommerceBase


class EmployeeORM(CommerceBase):
    __tablename__ = "commerce_employee"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    kind: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True, default="working")
    is_employed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    about_me: Mapped[str | None] = mapped_column(Text)
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
    education: Mapped[str | None] = mapped_column(Text)
    experience_text: Mapped[str | None] = mapped_column(Text)
    experience_start: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    auto_schedule_renewal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class EmployeeAvailabilityIntervalORM(CommerceBase):
    __tablename__ = "commerce_employee_availability_interval"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


class EmployeeLeaveORM(CommerceBase):
    __tablename__ = "commerce_employee_leave"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    leave_type: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    start: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    end: Mapped[date] = mapped_column(Date, nullable=False, index=True)
