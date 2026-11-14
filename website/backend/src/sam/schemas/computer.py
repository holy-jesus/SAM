from typing import Optional, List, Any
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from sam.schemas.installed_software import InstalledSoftwareResponse


class EmployeeSimpleResponse(BaseModel):
    id: str
    full_name: str
    email: Optional[str] = None
    department: Optional[str] = None
    position: Optional[str] = None
    status: str = "active"

    model_config = ConfigDict(from_attributes=True)


class ComputerBase(BaseModel):
    serial_number: str
    hostname: str
    ip_address: Optional[str] = None
    mac_address: Optional[str] = None
    os_name: Optional[str] = None
    os_version: Optional[str] = None
    cpu_info: Optional[str] = None
    ram_mb: Optional[int] = None
    disk_info: Optional[Any] = None
    is_online: bool = False
    employee_id: Optional[str] = None


class ComputerCreate(ComputerBase):
    pass


class ComputerUpdate(BaseModel):
    serial_number: Optional[str] = None
    hostname: Optional[str] = None
    ip_address: Optional[str] = None
    mac_address: Optional[str] = None
    os_name: Optional[str] = None
    os_version: Optional[str] = None
    cpu_info: Optional[str] = None
    ram_mb: Optional[int] = None
    disk_info: Optional[Any] = None
    is_online: Optional[bool] = None
    last_seen_at: Optional[datetime] = None
    employee_id: Optional[str] = None


class ComputerResponse(ComputerBase):
    id: str
    last_seen_at: Optional[datetime] = None
    installed_count: int = 0
    employee: Optional[EmployeeSimpleResponse] = None
    installed_software: Optional[List[InstalledSoftwareResponse]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
