from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sam.db import get_db
from sam.models.category import SoftwareCategory
from sam.schemas.category import (
    CategoryCreate,
    CategoryUpdate,
    CategoryResponse,
)

router = APIRouter(prefix="/categories", tags=["Categories"])


@router.get("", response_model=List[CategoryResponse])
async def get_categories(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SoftwareCategory).order_by(SoftwareCategory.id.asc()))
    categories = result.scalars().all()
    return categories


@router.post("", response_model=CategoryResponse)
async def create_category(payload: CategoryCreate, db: AsyncSession = Depends(get_db)):
    cat = SoftwareCategory(
        name=payload.name.strip(),
        description=payload.description,
        is_problematic=payload.is_problematic,
        risk_level=payload.risk_level,
        color_hex=payload.color_hex,
    )
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return cat


@router.put("/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: int, payload: CategoryUpdate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(SoftwareCategory).where(SoftwareCategory.id == category_id)
    )
    cat = result.scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="Категория не найдена")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(cat, field, value)

    await db.commit()
    await db.refresh(cat)
    return cat


@router.delete("/{category_id}")
async def delete_category(category_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SoftwareCategory).where(SoftwareCategory.id == category_id)
    )
    cat = result.scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="Категория не найдена")

    await db.delete(cat)
    await db.commit()
    return {"success": True}
