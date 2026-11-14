from typing import Optional
from datetime import datetime, date
from pydantic import BaseModel, ConfigDict


class RuSoftwareRegistryResponse(BaseModel):
    id: int
    reg_number: str
    name: str
    alternative_names: Optional[str] = None
    software_class: Optional[str] = None
    vendor_name: Optional[str] = None
    vendor_inn: Optional[str] = None
    documentation_url: Optional[str] = None
    is_ai: bool = False
    excluded_at: Optional[date] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class RegistryStatusResponse(BaseModel):
    last_updated_at: str
    total_records: int


class RegistrySyncResponse(BaseModel):
    success: bool
    message: str
    updated_count: int
