from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from sam.schemas.computer import ComputerResponse


class EmployeeBase(BaseModel):
    full_name: str
    email: Optional[str] = None
    department: Optional[str] = None
    position: Optional[str] = None
    status: str = "active"


class EmployeeCreate(EmployeeBase):
    pass


class EmployeeUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    department: Optional[str] = None
    position: Optional[str] = None
    status: Optional[str] = None


class EmployeeResponse(EmployeeBase):
    id: str
    computers_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class EmployeeDetailResponse(EmployeeResponse):
    computers: List[ComputerResponse] = []
