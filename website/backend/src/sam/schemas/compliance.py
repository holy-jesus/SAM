from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class ComplianceBalanceItem(BaseModel):
    software_id: str
    software_name: str
    vendor: Optional[str] = None
    license_type: str = "Commercial"
    purchased_count: int = 0
    installed_count: int = 0
    balance: int = 0  # purchased - installed
    unit_cost: float = 0.0
    total_penalty_risk_rub: float = 0.0
    status: str = "normal"  # 'normal', 'critical_overuse', 'underutilized'
    is_prohibited: bool = False


class ComplianceAlertResponse(BaseModel):
    id: str
    alert_type: str
    severity: str
    computer_id: Optional[str] = None
    computer_hostname: Optional[str] = None
    software_id: Optional[str] = None
    software_name: Optional[str] = None
    title: str
    description: str
    financial_risk_amount: float = 0.0
    status: str = "active"
    created_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class RecalculateResponse(BaseModel):
    success: bool
    recalculated_count: int
