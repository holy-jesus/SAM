from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sam.db import get_db
from sam.models.classifier import SoftwareClassifier
from sam.schemas.classifier import ClassifierResponse

router = APIRouter(prefix="/classifiers", tags=["Classifiers"])


@router.get("", response_model=List[ClassifierResponse])
async def get_classifiers(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SoftwareClassifier).order_by(SoftwareClassifier.code.asc())
    )
    classifiers = result.scalars().all()
    return classifiers
