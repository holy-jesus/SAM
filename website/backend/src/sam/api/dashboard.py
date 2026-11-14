from fastapi import APIRouter, Depends
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sam.db import get_db
from sam.models.computer import Computer
from sam.models.employee import Employee
from sam.models.installed_software import InstalledSoftware
from sam.models.compliance import ComplianceAlert
from sam.models.license import License
from sam.schemas.dashboard import DashboardSummary

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary", response_model=DashboardSummary)
async def get_dashboard_summary(db: AsyncSession = Depends(get_db)):
    # 1. Computers
    total_comps = (await db.execute(select(func.count(Computer.id)))).scalar_one()
    online_comps = (
        await db.execute(select(func.count(Computer.id)).where(Computer.is_online == True))
    ).scalar_one()
    offline_comps = total_comps - online_comps

    # 2. Employees
    total_emps = (await db.execute(select(func.count(Employee.id)))).scalar_one()

    # 3. Installed software
    total_installs = (
        await db.execute(
            select(func.count(InstalledSoftware.id)).where(InstalledSoftware.is_deleted == False)
        )
    ).scalar_one()

    # 4. Compliance alerts & Financial risk
    active_alerts_count = (
        await db.execute(
            select(func.count(ComplianceAlert.id)).where(ComplianceAlert.status == "active")
        )
    ).scalar_one()

    risk_sum = (
        await db.execute(
            select(func.sum(ComplianceAlert.financial_risk_amount)).where(
                ComplianceAlert.status == "active"
            )
        )
    ).scalar_one()
    total_financial_risk = float(risk_sum or 0.0)

    # 5. Licenses purchased
    purchased_count = (
        await db.execute(select(func.sum(License.total_purchased)))
    ).scalar_one() or 0

    # 6. Specific alert counts
    prohibited_count = (
        await db.execute(
            select(func.count(ComplianceAlert.id)).where(
                and_(
                    ComplianceAlert.status == "active",
                    ComplianceAlert.alert_type == "prohibited_software",
                )
            )
        )
    ).scalar_one()

    zombie_count = (
        await db.execute(
            select(func.count(ComplianceAlert.id)).where(
                and_(
                    ComplianceAlert.status == "active",
                    ComplianceAlert.alert_type == "zombie_software",
                )
            )
        )
    ).scalar_one()

    return {
        "total_computers": total_comps,
        "online_computers": online_comps,
        "offline_computers": offline_comps,
        "total_employees": total_emps,
        "total_installed_software_count": total_installs,
        "active_compliance_issues_count": active_alerts_count,
        "total_financial_risk_rub": total_financial_risk,
        "licenses_purchased_count": int(purchased_count),
        "prohibited_count": prohibited_count,
        "zombie_count": zombie_count,
    }


@router.get("/compliance-overview")
async def get_compliance_overview(db: AsyncSession = Depends(get_db)):
    alerts = (
        await db.execute(select(ComplianceAlert).where(ComplianceAlert.status == "active"))
    ).scalars().all()

    by_type = {}
    for a in alerts:
        by_type[a.alert_type] = by_type.get(a.alert_type, 0) + 1

    return {
        "total_active_alerts": len(alerts),
        "by_type": by_type,
    }
