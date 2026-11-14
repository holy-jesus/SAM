from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sam.db import get_db
from sam.models.compliance import ComplianceAlert
from sam.schemas.compliance import (
    ComplianceBalanceItem,
    ComplianceAlertResponse,
    RecalculateResponse,
)
from sam.services.compliance_engine import (
    get_compliance_balance_list,
    recalculate_compliance_alerts,
)

router = APIRouter(prefix="/compliance", tags=["Compliance"])


@router.get("/balance", response_model=List[ComplianceBalanceItem])
async def get_compliance_balance(db: AsyncSession = Depends(get_db)):
    return await get_compliance_balance_list(db)


@router.get("/alerts", response_model=List[ComplianceAlertResponse])
async def get_compliance_alerts(
    severity: Optional[str] = Query(None, description="Фильтр по уровню критичности (critical, warning, info, all)"),
    status: Optional[str] = Query("active", description="Статус алертов"),
    db: AsyncSession = Depends(get_db),
):
    query = select(ComplianceAlert)
    conditions = []

    if status and status != "all":
        conditions.append(ComplianceAlert.status == status)

    if severity and severity != "all":
        conditions.append(ComplianceAlert.severity == severity)

    if conditions:
        query = query.where(and_(*conditions))

    query = query.order_by(ComplianceAlert.created_at.desc())
    result = await db.execute(query)
    alerts = result.scalars().all()

    response = []
    for a in alerts:
        response.append({
            "id": str(a.id),
            "alert_type": a.alert_type,
            "severity": a.severity,
            "computer_id": str(a.computer_id) if a.computer_id else None,
            "computer_hostname": a.computer.hostname if a.computer else None,
            "software_id": str(a.software_id) if a.software_id else None,
            "software_name": a.software.name if a.software else None,
            "title": a.title,
            "description": a.description,
            "financial_risk_amount": float(a.financial_risk_amount),
            "status": a.status,
            "created_at": a.created_at,
            "resolved_at": a.resolved_at,
        })
    return response


@router.post("/recalculate", response_model=RecalculateResponse)
async def recalculate_compliance(db: AsyncSession = Depends(get_db)):
    count = await recalculate_compliance_alerts(db)
    return {"success": True, "recalculated_count": count}
