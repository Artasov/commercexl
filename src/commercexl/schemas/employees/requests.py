from datetime import datetime

from pydantic import BaseModel


class EmployeeAvailabilityRequest(BaseModel):
    start: datetime
    end: datetime


class EmployeeAvailabilityUpdateRequest(BaseModel):
    start: datetime | None = None
    end: datetime | None = None


