from typing import List, Optional
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sam.db import get_db
from sam.models.classifier import SoftwareClassifier
from sam.schemas.classifier import ClassifierResponse
from sam.services.registry_sync import sync_software_classifiers

router = APIRouter(prefix="/classifiers", tags=["Classifiers"])


@router.get("", response_model=List[ClassifierResponse])
async def get_classifiers(
    search: Optional[str] = None,
    section_code: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Возвращает список всех классов ПО РФ с группировкой по разделам.
    Поддерживает фильтрацию по поисковой строке и коду раздела.
    """
    query = select(SoftwareClassifier)
    if section_code:
        query = query.where(SoftwareClassifier.section_code == section_code)
    if search:
        s = f"%{search.strip().lower()}%"
        query = query.where(
            SoftwareClassifier.class_name.ilike(s)
            | SoftwareClassifier.code.ilike(s)
            | SoftwareClassifier.section_name.ilike(s)
        )
    result = await db.execute(query.order_by(SoftwareClassifier.code.asc()))
    classifiers = result.scalars().all()
    return classifiers


@router.post("/sync")
async def sync_classifiers(db: AsyncSession = Depends(get_db)):
    """
    Запускает синхронизацию справочника классификаторов ПО РФ:
    подтягивает актуальные данные из ru-ikt.ru/reestrpo и Единого реестра отечественного ПО.
    """
    stats = await sync_software_classifiers(db)
    return {
        "success": True,
        "message": f"Справочник классификаторов успешно синхронизирован: доступно {stats['total']} классов (добавлено новых: {stats['added']}, обновлено: {stats['updated']})",
        **stats,
    }

