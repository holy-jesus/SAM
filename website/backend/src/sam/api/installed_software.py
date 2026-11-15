import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sam.db import get_db
from sam.models.installed_software import InstalledSoftware
from sam.models.category import SoftwareCategory
from sam.models.process_signature import ProcessSignature
from sam.schemas.installed_software import (
    InstalledSoftwareResponse,
    UpdateSoftwareCategoryRequest,
)

router = APIRouter(prefix="/installed-software", tags=["Installed Software"])


def _serialize_installed(s: InstalledSoftware, sig: Optional[ProcessSignature] = None) -> dict:
    comp = s.computer
    cat_sw = s.catalog_software
    category = s.category

    is_domestic = bool(cat_sw and (cat_sw.ru_registry_id or getattr(cat_sw, "ru_registry", None)))
    has_sub = cat_sw.has_substitution if cat_sw else None
    sub_count = cat_sw.substitutions_count if cat_sw else 0

    norm_name = getattr(s, "normalized_name", None)
    m_source = getattr(s, "match_source", None)

    if not norm_name:
        if cat_sw:
            norm_name = cat_sw.name
            if not m_source:
                m_source = "catalog"
        elif sig:
            norm_name = sig.normalized_name
            if not m_source:
                m_source = sig.match_source

    return {
        "id": str(s.id),
        "computer_id": str(s.computer_id),
        "computer_hostname": comp.hostname if comp else None,
        "computer_serial": comp.serial_number if comp else None,
        "raw_display_name": s.raw_display_name,
        "raw_publisher": s.raw_publisher,
        "raw_version": s.raw_version,
        "install_path": s.install_path,
        "binary_hash": s.binary_hash,
        "last_launched_at": s.last_launched_at,
        "source": s.source,
        "catalog_software_id": str(s.catalog_software_id) if s.catalog_software_id else None,
        "catalog_software_name": cat_sw.name if cat_sw else None,
        "normalized_name": norm_name,
        "match_source": m_source,
        "category_id": s.category_id,
        "category_name": category.name if category else None,
        "is_problematic": category.is_problematic if category else False,
        "match_confidence": s.match_confidence,
        "is_verified_by_admin": s.is_verified_by_admin,
        "is_deleted": s.is_deleted,
        "has_substitution": has_sub,
        "substitutions_count": sub_count,
        "is_domestic": is_domestic,
        "first_seen_at": s.first_seen_at,
        "last_seen_at": s.last_seen_at,
    }


@router.get("", response_model=List[InstalledSoftwareResponse])
async def get_installed_software(
    search: Optional[str] = Query(None),
    category_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    query = select(InstalledSoftware).where(InstalledSoftware.is_deleted == False)
    conditions = []

    if search:
        s = f"%{search.strip().lower()}%"
        conditions.append(
            or_(
                func.lower(InstalledSoftware.raw_display_name).like(s),
                func.lower(InstalledSoftware.raw_publisher).like(s),
                func.lower(InstalledSoftware.normalized_name).like(s),
            )
        )

    if category_id is not None:
        conditions.append(InstalledSoftware.category_id == category_id)

    if conditions:
        query = query.where(and_(*conditions))

    query = query.order_by(InstalledSoftware.raw_display_name.asc())
    result = await db.execute(query)
    items = result.scalars().all()

    # Загружаем сигнатуры процессов для обогащения, если в базе ещё не заполнен normalized_name
    sig_stmt = select(ProcessSignature)
    sig_res = await db.execute(sig_stmt)
    signatures = sig_res.scalars().all()
    sig_by_proc = {sig.process_name.lower(): sig for sig in signatures}

    return [_serialize_installed(i, sig_by_proc.get(i.raw_display_name.lower())) for i in items]


@router.put("/{installed_id}/category", response_model=InstalledSoftwareResponse)
async def update_installed_software_category(
    installed_id: str,
    payload: UpdateSoftwareCategoryRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        iid = uuid.UUID(installed_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат UUID")

    result = await db.execute(
        select(InstalledSoftware).where(InstalledSoftware.id == iid)
    )
    inst = result.scalar_one_or_none()
    if not inst:
        raise HTTPException(status_code=404, detail="Запись об установленном ПО не найдена")

    cat_res = await db.execute(
        select(SoftwareCategory).where(SoftwareCategory.id == payload.category_id)
    )
    cat = cat_res.scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="Категория не найдена")

    inst.category_id = cat.id
    inst.is_verified_by_admin = True
    await db.commit()
    await db.refresh(inst)

    return _serialize_installed(inst)
