from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sam.db import get_db
from sam.models.registry import RuSoftwareRegistry
from sam.schemas.registry import (
    RuSoftwareRegistryResponse,
    RegistryStatusResponse,
    RegistrySyncResponse,
)
from sam.services.registry_sync import sync_russian_registry

router = APIRouter(prefix="/registry", tags=["Russian Software Registry"])


@router.get("", response_model=List[RuSoftwareRegistryResponse])
async def get_registry(
    search: Optional[str] = Query(None, description="Поиск по названию или рег. номеру"),
    class_code: Optional[str] = Query(None, description="Фильтр по классу ПО"),
    limit: int = Query(100, ge=1, le=500),
    page: int = Query(1, ge=1),
    db: AsyncSession = Depends(get_db),
):
    query = select(RuSoftwareRegistry)
    conditions = []

    if search:
        s = f"%{search.strip().lower()}%"
        conditions.append(
            or_(
                func.lower(RuSoftwareRegistry.name).like(s),
                func.lower(RuSoftwareRegistry.reg_number).like(s),
                func.lower(RuSoftwareRegistry.alternative_names).like(s),
                func.lower(RuSoftwareRegistry.vendor_name).like(s),
            )
        )

    if class_code:
        conditions.append(RuSoftwareRegistry.software_class.like(f"%{class_code.strip()}%"))

    if conditions:
        query = query.where(and_(*conditions))

    offset = (page - 1) * limit
    query = query.order_by(RuSoftwareRegistry.id.asc()).offset(offset).limit(limit)
    result = await db.execute(query)
    items = result.scalars().all()
    return items


@router.get("/status", response_model=RegistryStatusResponse)
async def get_registry_status(db: AsyncSession = Depends(get_db)):
    total = (await db.execute(select(func.count(RuSoftwareRegistry.id)))).scalar_one()
    latest_upd = (
        await db.execute(select(func.max(RuSoftwareRegistry.updated_at)))
    ).scalar_one()

    last_str = latest_upd.isoformat() if latest_upd else datetime.now(timezone.utc).isoformat()
    return {
        "last_updated_at": last_str,
        "total_records": total,
    }


@router.post("/sync", response_model=RegistrySyncResponse)
async def sync_registry(db: AsyncSession = Depends(get_db)):
    updated_count = await sync_russian_registry(db)
    return {
        "success": True,
        "message": "Единый реестр отечественного ПО успешно синхронизирован с reestr.digital.gov.ru",
        "updated_count": updated_count,
    }
