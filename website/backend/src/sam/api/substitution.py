import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sam.db import get_db
from sam.models.catalog import SoftwareCatalog
from sam.schemas.substitution import (
    SubstitutionItemResponse,
    SubstitutionSearchResponse,
    SubstitutionSyncResponse,
)
from sam.services.substitution_service import (
    search_import_substitutions,
    fetch_product_suggestions,
    fetch_live_substitution,
    parse_substitution_html,
    save_substitution_items_to_db,
)

router = APIRouter(prefix="/substitution", tags=["Import Substitution"])


@router.get("/search", response_model=SubstitutionSearchResponse)
async def search_substitutions(
    query: str = Query(..., description="Название импортного ПО (например, 'Photoshop', 'AutoCAD', 'Oracle')"),
    force_fetch: bool = Query(False, description="Принудительно запросить онлайн с reestr.digital.gov.ru"),
    db: AsyncSession = Depends(get_db),
):
    """
    Поиск отечественных аналогов для зарубежного ПО:
    выполняет HTTP-запрос к reestr.digital.gov.ru по образцу HAR-дампа браузера,
    парсит HTML-страницу и кэширует результаты в БД.
    """
    items = await search_import_substitutions(db, query=query, force_fetch=force_fetch)
    return {
        "query": query,
        "total_found": len(items),
        "items": [
            SubstitutionItemResponse(
                id=str(it.id),
                foreign_software_name=it.foreign_software_name,
                russian_software_name=it.russian_software_name,
                russian_reg_number=it.russian_reg_number,
                source=it.source,
                owner_name=it.owner_name,
                class_code=it.class_code,
                class_name=it.class_name,
                registration_date=it.registration_date,
                registry_url=it.registry_url,
                ru_registry_id=it.ru_registry_id,
                catalog_software_id=str(it.catalog_software_id) if it.catalog_software_id else None,
                created_at=it.created_at,
            )
            for it in items
        ],
    }


@router.get("/suggestions", response_model=List[str])
async def get_suggestions(
    query: str = Query(..., description="Часть названия ПО для автодополнения (Bitrix AJAX API)"),
):
    """
    Получение подсказок названий иностранного ПО через AJAX эндпоинт reestr.digital.gov.ru
    (воспроизводит запрос Entry 1 из HAR).
    """
    suggestions = fetch_product_suggestions(query)
    return suggestions


@router.get("/catalog/{catalog_software_id}", response_model=SubstitutionSearchResponse)
async def get_catalog_substitutions(
    catalog_software_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Возвращает рекомендуемые российские аналоги для позиции корпоративного каталога ПО.
    """
    cat_sw = (
        await db.execute(select(SoftwareCatalog).where(SoftwareCatalog.id == catalog_software_id))
    ).scalar_one_or_none()

    if not cat_sw:
        raise HTTPException(status_code=404, detail="ПО в каталоге не найдено")

    items = await search_import_substitutions(db, query=cat_sw.name)
    return {
        "query": cat_sw.name,
        "total_found": len(items),
        "items": [
            SubstitutionItemResponse(
                id=str(it.id),
                foreign_software_name=it.foreign_software_name,
                russian_software_name=it.russian_software_name,
                russian_reg_number=it.russian_reg_number,
                source=it.source,
                owner_name=it.owner_name,
                class_code=it.class_code,
                class_name=it.class_name,
                registration_date=it.registration_date,
                registry_url=it.registry_url,
                ru_registry_id=it.ru_registry_id,
                catalog_software_id=str(it.catalog_software_id) if it.catalog_software_id else None,
                created_at=it.created_at,
            )
            for it in items
        ],
    }


@router.post("/fetch-online", response_model=SubstitutionSyncResponse)
async def fetch_online_substitution(
    query: str = Query(..., description="Название зарубежного ПО для парсинга с reestr.digital.gov.ru"),
    db: AsyncSession = Depends(get_db),
):
    """
    Выполняет прямой запрос к reestr.digital.gov.ru/import-substitution/?query=...,
    парсит HTML и сохраняет результаты в базу данных.
    """
    html_content = fetch_live_substitution(query)
    if not html_content:
        return {
            "success": False,
            "imported_count": 0,
            "message": f"Не удалось получить ответ от reestr.digital.gov.ru для '{query}' (сеть недоступна).",
        }

    items = parse_substitution_html(html_content, foreign_query=query)
    count = await save_substitution_items_to_db(db, items)
    return {
        "success": True,
        "imported_count": count,
        "message": f"Успешно получено и сохранено {count} отечественных аналогов для '{query}'.",
    }
