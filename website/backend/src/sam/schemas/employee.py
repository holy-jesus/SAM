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
    user_category: Optional[str] = None


class EmployeeCreate(EmployeeBase):
    pass


class EmployeeUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    department: Optional[str] = None
    position: Optional[str] = None
    status: Optional[str] = None
    user_category: Optional[str] = None


class EmployeeResponse(EmployeeBase):
    id: str
    computers_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class EmployeeDetailResponse(EmployeeResponse):
    computers: List[ComputerResponse] = []


class EmployeeCategoryBase(BaseModel):
    name: str
    description: Optional[str] = None
    allowed_software_list: Optional[str] = None


class EmployeeCategoryCreate(EmployeeCategoryBase):
    pass


class EmployeeCategoryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    allowed_software_list: Optional[str] = None


class EmployeeCategoryResponse(EmployeeCategoryBase):
    id: int
    employees_count: int = 0

    model_config = ConfigDict(from_attributes=True)

