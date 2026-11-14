import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sam.db import get_db
from sam.models.catalog import SoftwareCatalog
from sam.models.installed_software import InstalledSoftware
from sam.schemas.catalog import (
    CatalogItemCreate,
    CatalogItemUpdate,
    CatalogItemResponse,
)

router = APIRouter(prefix="/catalog", tags=["Software Catalog"])


def _serialize_catalog_item(item: SoftwareCatalog) -> dict:
    classifier = None
    if item.classifier:
        classifier = {
            "id": item.classifier.id,
            "code": item.classifier.code,
            "section_code": item.classifier.section_code,
            "section_name": item.classifier.section_name,
            "class_name": item.classifier.class_name,
        }

    ru_reg = None
    if item.ru_registry:
        ru_reg = {
            "id": item.ru_registry.id,
            "reg_number": item.ru_registry.reg_number,
            "name": item.ru_registry.name,
            "alternative_names": item.ru_registry.alternative_names,
            "software_class": item.ru_registry.software_class,
            "vendor_name": item.ru_registry.vendor_name,
            "vendor_inn": item.ru_registry.vendor_inn,
            "documentation_url": item.ru_registry.documentation_url,
            "is_ai": item.ru_registry.is_ai,
            "excluded_at": item.ru_registry.excluded_at,
            "updated_at": item.ru_registry.updated_at,
        }

    cat = None
    if item.category:
        cat = {
            "id": item.category.id,
            "name": item.category.name,
            "description": item.category.description,
            "is_problematic": item.category.is_problematic,
            "risk_level": item.category.risk_level,
            "color_hex": item.category.color_hex,
        }

    return {
        "id": str(item.id),
        "name": item.name,
        "vendor": item.vendor,
        "description": item.description,
        "classifier_id": item.classifier_id,
        "ru_registry_id": item.ru_registry_id,
        "category_id": item.category_id,
        "license_type": item.license_type,
        "max_installations": item.max_installations,
        "responsible_person": item.responsible_person,
        "approval_status": item.approval_status,
        "active_installations_count": len(item.installations) if item.installations else 0,
        "classifier": classifier,
        "ru_registry": ru_reg,
        "category": cat,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


@router.get("", response_model=List[CatalogItemResponse])
async def get_catalog(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SoftwareCatalog).order_by(SoftwareCatalog.name.asc()))
    items = result.scalars().all()
    return [_serialize_catalog_item(i) for i in items]


@router.post("", response_model=CatalogItemResponse)
async def create_catalog_item(payload: CatalogItemCreate, db: AsyncSession = Depends(get_db)):
    item = SoftwareCatalog(
        name=payload.name.strip(),
        vendor=payload.vendor.strip() if payload.vendor else None,
        description=payload.description,
        classifier_id=payload.classifier_id,
        ru_registry_id=payload.ru_registry_id,
        category_id=payload.category_id or 1,
        license_type=payload.license_type,
        max_installations=payload.max_installations,
        responsible_person=payload.responsible_person,
        approval_status=payload.approval_status,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return _serialize_catalog_item(item)


@router.get("/{item_id}", response_model=CatalogItemResponse)
async def get_catalog_item(item_id: str, db: AsyncSession = Depends(get_db)):
    try:
        uid = uuid.UUID(item_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат UUID")

    result = await db.execute(select(SoftwareCatalog).where(SoftwareCatalog.id == uid))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="ПО не найдено в каталоге")
    return _serialize_catalog_item(item)


@router.put("/{item_id}", response_model=CatalogItemResponse)
async def update_catalog_item(
    item_id: str, payload: CatalogItemUpdate, db: AsyncSession = Depends(get_db)
):
    try:
        uid = uuid.UUID(item_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат UUID")

    result = await db.execute(select(SoftwareCatalog).where(SoftwareCatalog.id == uid))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="ПО не найдено в каталоге")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(item, field, value)

    await db.commit()
    await db.refresh(item)
    return _serialize_catalog_item(item)


@router.delete("/{item_id}")
async def delete_catalog_item(item_id: str, db: AsyncSession = Depends(get_db)):
    try:
        uid = uuid.UUID(item_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат UUID")

    result = await db.execute(select(SoftwareCatalog).where(SoftwareCatalog.id == uid))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="ПО не найдено в каталоге")

    await db.delete(item)
    await db.commit()
    return {"success": True}
