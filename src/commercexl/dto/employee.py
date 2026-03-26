from pydantic import BaseModel


class EmployeeAvailabilityDTO(BaseModel):
    id: int
    user: int
    start: str
    end: str


