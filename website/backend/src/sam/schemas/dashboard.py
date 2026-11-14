from typing import Optional
from pydantic import BaseModel


class DashboardSummary(BaseModel):
    total_computers: int = 0
    online_computers: int = 0
    offline_computers: int = 0
    total_employees: int = 0
    total_installed_software_count: int = 0
    active_compliance_issues_count: int = 0
    total_financial_risk_rub: float = 0.0
    licenses_purchased_count: Optional[int] = 0
    prohibited_count: Optional[int] = 0
    zombie_count: Optional[int] = 0
