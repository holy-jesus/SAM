from typing import Optional, Any
from datetime import datetime, date
from decimal import Decimal
from pydantic import BaseModel, ConfigDict


class LicenseBase(BaseModel):
    software_id: str
    license_name: str
    license_type: str = "Платный"
    license_model: str = "per_device"
    total_purchased: int = 1
    unit_cost: Decimal = Decimal("0.00")
    currency: str = "RUB"
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    eula_text: Optional[str] = None


class LicenseCreate(LicenseBase):
    pass


class LicenseUpdate(BaseModel):
    software_id: Optional[str] = None
    license_name: Optional[str] = None
    license_type: Optional[str] = None
    license_model: Optional[str] = None
    total_purchased: Optional[int] = None
    unit_cost: Optional[Decimal] = None
    currency: Optional[str] = None
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    eula_text: Optional[str] = None
    eula_analysis: Optional[Any] = None


class LicenseResponse(BaseModel):
    id: str
    software_id: str
    software_name: Optional[str] = None
    license_name: str
    license_type: str
    license_model: str
    total_purchased: int
    unit_cost: float
    currency: str
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    eula_text: Optional[str] = None
    eula_analysis: Optional[Any] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
