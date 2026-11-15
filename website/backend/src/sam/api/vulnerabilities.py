import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, or_, and_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from sam.db import get_db
from sam.models.vulnerability import Vulnerability
from sam.models.installed_software import InstalledSoftware
from sam.schemas.vulnerability import (
    VulnerabilityItemResponse,
    VulnerabilitiesListResponse,
    VulnerabilitiesSummaryResponse,
    ComputerVulnerabilitiesResponse,
    VulnerabilitySyncResponse,
)
from sam.services.vulnerability_service import (
    sync_vulnerabilities_from_file,
    find_vulnerabilities_for_software,
    get_computer_vulnerabilities_report,
    get_vulnerabilities_summary,
)

router = APIRouter(prefix="/vulnerabilities", tags=["Vulnerabilities (FSTEC BDU)"])


@router.get("", response_model=VulnerabilitiesListResponse)
async def get_vulnerabilities(
    search: Optional[str] = Query(None, description="Поиск по BDU, CVE, вендору или названию ПО"),
    severity: Optional[str] = Query(None, description="Фильтр по уровню опасности (Критический, Высокий, Средний, Низкий)"),
    vendor: Optional[str] = Query(None, description="Фильтр по вендору"),
    has_exploit: Optional[bool] = Query(None, description="Только с подтвержденным эксплойтом"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """
    Список уязвимостей безопасности из базы БДУ ФСТЭК России с фильтрацией и пагинацией.
    """
    conditions = []
    if search:
        s = f"%{search.strip().lower()}%"
        conditions.append(
            or_(
                func.lower(Vulnerability.bdu_id).like(s),
                func.lower(Vulnerability.cve_id).like(s),
                func.lower(Vulnerability.vendor).like(s),
                func.lower(Vulnerability.software_name).like(s),
                func.lower(Vulnerability.name).like(s),
            )
        )
    if severity:
        conditions.append(Vulnerability.severity == severity.strip())
    if vendor:
        conditions.append(func.lower(Vulnerability.vendor).like(f"%{vendor.strip().lower()}%"))
    if has_exploit is True:
        conditions.append(Vulnerability.exploit_status.ilike("%существ%"))

    query = select(Vulnerability)
    count_query = select(func.count(Vulnerability.id))

    if conditions:
        query = query.where(and_(*conditions))
        count_query = count_query.where(and_(*conditions))

    total = (await db.execute(count_query)).scalar_one()

    offset = (page - 1) * limit
    query = (
        query.order_by(
            Vulnerability.cvss_score.desc().nullslast(),
            desc(Vulnerability.severity == "Критический"),
            desc(Vulnerability.severity == "Высокий"),
        )
        .offset(offset)
        .limit(limit)
    )

    items = (await db.execute(query)).scalars().all()

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "items": [
            VulnerabilityItemResponse(
                id=str(it.id),
                bdu_id=it.bdu_id,
                name=it.name,
                description=it.description,
                vendor=it.vendor,
                software_name=it.software_name,
                software_version=it.software_version,
                software_type=it.software_type,
                vuln_class=it.vuln_class,
                severity=it.severity,
                cvss_score=it.cvss_score,
                solution=it.solution,
                status=it.status,
                exploit_status=it.exploit_status,
                cve_id=it.cve_id,
                publish_date=it.publish_date,
                created_at=it.created_at,
            )
            for it in items
        ],
    }


@router.get("/summary", response_model=VulnerabilitiesSummaryResponse)
async def get_summary(db: AsyncSession = Depends(get_db)):
    """
    Сводная статистика по уязвимостям: общее количество, критические, высокие и наличие эксплойтов.
    """
    summary = await get_vulnerabilities_summary(db)
    return summary


@router.get("/computer/{computer_id}", response_model=ComputerVulnerabilitiesResponse)
async def get_computer_vulnerabilities(
    computer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Возвращает отчет об уязвимостях для конкретного компьютера на основе фактически установленного ПО.
    """
    report = await get_computer_vulnerabilities_report(db, computer_id)
    if "error" in report:
        raise HTTPException(status_code=404, detail=report["error"])
    return report


@router.get("/software/{installed_software_id}", response_model=List[VulnerabilityItemResponse])
async def get_installed_software_vulnerabilities(
    installed_software_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Возвращает список уязвимостей БДУ ФСТЭК для конкретной инсталляции программы.
    """
    sw = (
        await db.execute(
            select(InstalledSoftware).where(InstalledSoftware.id == installed_software_id)
        )
    ).scalar_one_or_none()

    if not sw:
        raise HTTPException(status_code=404, detail="Установленное ПО не найдено")

    vulns = await find_vulnerabilities_for_software(
        db=db,
        display_name=sw.raw_display_name,
        publisher=sw.raw_publisher,
        version=sw.raw_version,
        limit=50,
    )

    return [
        VulnerabilityItemResponse(
            id=str(v.id),
            bdu_id=v.bdu_id,
            name=v.name,
            description=v.description,
            vendor=v.vendor,
            software_name=v.software_name,
            software_version=v.software_version,
            software_type=v.software_type,
            vuln_class=v.vuln_class,
            severity=v.severity,
            cvss_score=v.cvss_score,
            solution=v.solution,
            status=v.status,
            exploit_status=v.exploit_status,
            cve_id=v.cve_id,
            publish_date=v.publish_date,
            created_at=v.created_at,
        )
        for v in vulns
    ]


@router.post("/sync", response_model=VulnerabilitySyncResponse)
async def sync_vulnerabilities(
    limit: Optional[int] = Query(None, description="Лимит строк для синхронизации (по умолчанию без ограничений)"),
    db: AsyncSession = Depends(get_db),
):
    """
    Запускает парсинг и синхронизацию базы данных уязвимостей БДУ ФСТЭК России
    из файла data/уязвимости.xlsx или с официального сайта bdu.fstec.ru.
    """
    count = await sync_vulnerabilities_from_file(db, limit_rows=limit)
    return {
        "success": True,
        "imported_count": count,
        "message": f"Успешно синхронизировано {count} уязвимостей БДУ ФСТЭК России.",
    }
