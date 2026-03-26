from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from commercexl.dto import EmployeeAvailabilityDTO
from commercexl.models import EmployeeAvailabilityIntervalORM
from commercexl.services.base_runtime import BaseRuntime


class Employee(BaseRuntime):
    """Р Р°СЃРїРёСЃР°РЅРёРµ РґРѕСЃС‚СѓРїРЅРѕСЃС‚Рё СЃРѕС‚СЂСѓРґРЅРёРєРѕРІ РґР»СЏ commerce-СЃС†РµРЅР°СЂРёРµРІ."""

    @staticmethod
    def serialize_employee_availability(item: EmployeeAvailabilityIntervalORM) -> EmployeeAvailabilityDTO:
        return EmployeeAvailabilityDTO(
            id=item.id, user=item.user_id, start=item.start.isoformat(), end=item.end.isoformat(),
        )

    async def list_employee_availability(self, session: AsyncSession, user_id: int) -> list[EmployeeAvailabilityDTO]:
        query = select(EmployeeAvailabilityIntervalORM).where(
            EmployeeAvailabilityIntervalORM.user_id == user_id,
        ).order_by(
            EmployeeAvailabilityIntervalORM.start.asc(),
        )
        items = list((await session.execute(query)).scalars())
        return [self.serialize_employee_availability(item) for item in items]

    @staticmethod
    async def is_employee_availability_overlap(
            session: AsyncSession, user_id: int, start: datetime, end: datetime, interval_id: int | None = None
    ) -> bool:
        """РџСЂРѕРІРµСЂСЏРµС‚, РїРµСЂРµСЃРµРєР°РµС‚СЃСЏ Р»Рё РЅРѕРІС‹Р№ РёРЅС‚РµСЂРІР°Р» СЃ СѓР¶Рµ СЃРѕС…СЂР°РЅС‘РЅРЅС‹РјРё РёРЅС‚РµСЂРІР°Р»Р°РјРё СЃРѕС‚СЂСѓРґРЅРёРєР°."""
        query = select(EmployeeAvailabilityIntervalORM.id).where(
            EmployeeAvailabilityIntervalORM.user_id == user_id,
            or_(
                and_(EmployeeAvailabilityIntervalORM.start <= start, EmployeeAvailabilityIntervalORM.end > start),
                and_(EmployeeAvailabilityIntervalORM.start < end, EmployeeAvailabilityIntervalORM.end >= end),
                and_(EmployeeAvailabilityIntervalORM.start >= start, EmployeeAvailabilityIntervalORM.end <= end),
            ),
        )
        if interval_id is not None:
            query = query.where(EmployeeAvailabilityIntervalORM.id != interval_id)
        return (await session.execute(query.limit(1))).scalar_one_or_none() is not None

    async def create_employee_availability(
            self, session: AsyncSession, user_id: int, start: datetime, end: datetime
    ) -> EmployeeAvailabilityDTO:
        if await self.is_employee_availability_overlap(session, user_id, start, end):
            raise self.get_bad_request("The selected time overlaps with an existing availability interval.")
        interval = EmployeeAvailabilityIntervalORM(user_id=user_id, start=start, end=end)
        session.add(interval)
        await session.flush()
        return self.serialize_employee_availability(interval)

    async def update_employee_availability(
            self, session: AsyncSession, user_id: int, interval_id: int, start: datetime, end: datetime
    ) -> EmployeeAvailabilityDTO:
        interval: EmployeeAvailabilityIntervalORM | None = await session.get(
            EmployeeAvailabilityIntervalORM, interval_id,
        )
        if interval is None or interval.user_id != user_id:
            raise self.get_not_found("Availability interval not found.")
        existing_interval_id = interval.id
        if await self.is_employee_availability_overlap(session, user_id, start, end, interval_id=existing_interval_id):
            raise self.get_bad_request("The selected time overlaps with an existing availability interval.")
        interval.start = start
        interval.end = end
        await session.flush()
        return self.serialize_employee_availability(interval)

    async def delete_employee_availability(self, session: AsyncSession, user_id: int, interval_id: int) -> None:
        interval: EmployeeAvailabilityIntervalORM | None = await session.get(
            EmployeeAvailabilityIntervalORM, interval_id,
        )
        if interval is None or interval.user_id != user_id:
            raise self.get_not_found("Availability interval not found.")
        await session.delete(interval)


