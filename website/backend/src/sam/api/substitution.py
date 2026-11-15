import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sam.db import get_db
from sam.models.catalog import SoftwareCatalog
from sam.models.substitution import SubstitutionCache
from sam.schemas.substitution import (
    SubstitutionItemResponse,
    SubstitutionSearchResponse,
    SubstitutionSyncResponse,
    SubstitutionStatusResponse,
    SubstitutionCacheItemResponse,
)
from sam.services.substitution_service import (
    search_import_substitutions,
    fetch_product_suggestions,
    fetch_live_substitution,
    parse_substitution_html,
    save_substitution_items_to_db,
    process_software_substitution,
    scan_and_queue_unprocessed_catalog,
    get_cached_substitution_status,
    check_is_in_ru_registry,
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
    Выполняет запрос к reestr.digital.gov.ru/import-substitution/?query=...
    с контролем Rate Limiter, парсит HTML и сохраняет результаты и кэш в БД.
    """
    res = await process_software_substitution(db, software_name=query, force_fetch=True)
    count = res.get("substitutions_count", 0)
    status = res.get("status", "")

    if status == "domestic":
        return {
            "success": True,
            "imported_count": 0,
            "message": f"'{query}' входит в Единый реестр отечественного ПО РФ (импортозамещение не требуется).",
        }

    if status == "error":
        return {
            "success": False,
            "imported_count": 0,
            "message": f"Не удалось получить ответ от reestr.digital.gov.ru для '{query}' (сеть недоступна или сработал rate-limit).",
        }

    return {
        "success": True,
        "imported_count": count,
        "message": f"Успешно обработано: {count} отечественных аналогов для '{query}'.",
    }


@router.get("/status/{software_name}", response_model=SubstitutionStatusResponse)
async def get_software_substitution_status(
    software_name: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Возвращает статус проверки импортозамещения для конкретного ПО:
    отечественное (реестр РФ), есть аналоги в РФ, аналогов нет, либо проверка ещё не проводилась.
    """
    clean_name = software_name.strip()

    # 1. Проверяем Реестр РФ
    is_domestic, _ = await check_is_in_ru_registry(db, clean_name)
    if is_domestic:
        return {
            "software_name": clean_name,
            "status": "domestic",
            "has_substitution": False,
            "substitutions_count": 0,
            "is_domestic": True,
            "message": "ПО зарегистрировано в Едином реестре РФ (отечественное)",
        }

    # 2. Проверяем кэш в БД
    cached = await get_cached_substitution_status(db, clean_name)
    if cached:
        return {
            "software_name": clean_name,
            "status": cached.status,
            "has_substitution": cached.has_substitution,
            "substitutions_count": cached.substitutions_count,
            "is_domestic": cached.is_domestic,
            "last_checked_at": cached.last_checked_at,
            "expires_at": cached.expires_at,
            "message": f"Найдено {cached.substitutions_count} аналогов" if cached.has_substitution else "Аналогов в реестре не найдено",
        }

    return {
        "software_name": clean_name,
        "status": "not_checked",
        "has_substitution": False,
        "substitutions_count": 0,
        "is_domestic": False,
        "message": "Проверка ещё не выполнялась",
    }


@router.post("/scan-catalog")
async def scan_catalog_substitutions(db: AsyncSession = Depends(get_db)):
    """
    Запускает сканирование корпоративного каталога ПО:
    находит всё зарубежное ПО без кэша и ставит в очередь фоновой проверки с rate-limit.
    """
    count = await scan_and_queue_unprocessed_catalog(db)
    return {
        "enqueued_count": count,
        "message": f"Поставлено в очередь на фоновую проверку {count} позиций зарубежного ПО.",
    }


@router.get("/cache", response_model=List[SubstitutionCacheItemResponse])
async def get_substitution_cache(
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """
    Возвращает список закэшированных проверок импортозамещения из таблицы substitution_cache.
    """
    stmt = (
        select(SubstitutionCache)
        .order_by(SubstitutionCache.last_checked_at.desc())
        .limit(limit)
    )
    items = (await db.execute(stmt)).scalars().all()
    return [
        SubstitutionCacheItemResponse(
            id=str(it.id),
            software_name=it.software_name,
            has_substitution=it.has_substitution,
            substitutions_count=it.substitutions_count,
            is_domestic=it.is_domestic,
            status=it.status,
            catalog_software_id=str(it.catalog_software_id) if it.catalog_software_id else None,
            last_checked_at=it.last_checked_at,
            expires_at=it.expires_at,
            error_message=it.error_message,
        )
        for it in items
    ]
