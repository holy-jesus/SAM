import uuid
from decimal import Decimal
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sam.db import get_db
from sam.models.license import License
from sam.models.catalog import SoftwareCatalog
from sam.schemas.license import (
    LicenseCreate,
    LicenseUpdate,
    LicenseResponse,
)

router = APIRouter(prefix="/licenses", tags=["Licenses"])


def _serialize_license(lic: License) -> dict:
    return {
        "id": str(lic.id),
        "software_id": str(lic.software_id),
        "software_name": lic.software.name if lic.software else None,
        "license_name": lic.license_name,
        "license_type": lic.license_type,
        "license_model": lic.license_model,
        "total_purchased": lic.total_purchased,
        "unit_cost": float(lic.unit_cost),
        "currency": lic.currency,
        "valid_from": lic.valid_from,
        "valid_to": lic.valid_to,
        "eula_text": lic.eula_text,
        "eula_analysis": lic.eula_analysis,
        "created_at": lic.created_at,
        "updated_at": lic.updated_at,
    }


@router.get("", response_model=List[LicenseResponse])
async def get_licenses(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(License).order_by(License.created_at.desc()))
    licenses = result.scalars().all()
    return [_serialize_license(l) for l in licenses]


@router.post("", response_model=LicenseResponse)
async def create_license(payload: LicenseCreate, db: AsyncSession = Depends(get_db)):
    try:
        sw_id = uuid.UUID(payload.software_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат UUID ПО")

    sw_res = await db.execute(select(SoftwareCatalog).where(SoftwareCatalog.id == sw_id))
    if not sw_res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="ПО для лицензии не найдено в каталоге")

    lic = License(
        software_id=sw_id,
        license_name=payload.license_name.strip(),
        license_type=payload.license_type,
        license_model=payload.license_model,
        total_purchased=payload.total_purchased,
        unit_cost=payload.unit_cost,
        currency=payload.currency,
        valid_from=payload.valid_from,
        valid_to=payload.valid_to,
        eula_text=payload.eula_text,
    )
    db.add(lic)
    await db.commit()
    await db.refresh(lic)
    return _serialize_license(lic)


@router.get("/{license_id}", response_model=LicenseResponse)
async def get_license(license_id: str, db: AsyncSession = Depends(get_db)):
    try:
        lid = uuid.UUID(license_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат UUID")

    result = await db.execute(select(License).where(License.id == lid))
    lic = result.scalar_one_or_none()
    if not lic:
        raise HTTPException(status_code=404, detail="Лицензия не найдена")
    return _serialize_license(lic)


@router.put("/{license_id}", response_model=LicenseResponse)
async def update_license(
    license_id: str, payload: LicenseUpdate, db: AsyncSession = Depends(get_db)
):
    try:
        lid = uuid.UUID(license_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат UUID")

    result = await db.execute(select(License).where(License.id == lid))
    lic = result.scalar_one_or_none()
    if not lic:
        raise HTTPException(status_code=404, detail="Лицензия не найдена")

    update_data = payload.model_dump(exclude_unset=True)
    if "software_id" in update_data:
        raw_sw_id = update_data.pop("software_id")
        lic.software_id = uuid.UUID(raw_sw_id)

    for field, value in update_data.items():
        setattr(lic, field, value)

    await db.commit()
    await db.refresh(lic)
    return _serialize_license(lic)


@router.delete("/{license_id}")
async def delete_license(license_id: str, db: AsyncSession = Depends(get_db)):
    try:
        lid = uuid.UUID(license_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат UUID")

    result = await db.execute(select(License).where(License.id == lid))
    lic = result.scalar_one_or_none()
    if not lic:
        raise HTTPException(status_code=404, detail="Лицензия не найдена")

    await db.delete(lic)
    await db.commit()
    return {"success": True}
