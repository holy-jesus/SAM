from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sam.models.category import SoftwareCategory
from sam.models.classifier import SoftwareClassifier
from sam.models.vulnerability import Vulnerability
from sam.services.registry_sync import sync_software_classifiers, sync_russian_registry
from sam.services.compliance_engine import recalculate_compliance_alerts
from sam.services.vulnerability_service import sync_vulnerabilities_from_file


async def seed_database_if_empty(db: AsyncSession):
    # 1. Категории ПО (Актуальный / Устаревший / Запрещённый)
    # Это справочные данные, не заглушки: без них система неработоспособна
    cat_count = await db.execute(select(func.count(SoftwareCategory.id)))
    if cat_count.scalar_one() == 0:
        default_categories = [
            SoftwareCategory(
                id=1,
                name="Актуальный",
                description="Разрешённое к повсеместному использованию актуальное ПО",
                is_problematic=False,
                risk_level="none",
                color_hex="#10B981",
            ),
            SoftwareCategory(
                id=2,
                name="Устаревший",
                description="ПО с завершённым жизненным циклом вендора (EoL). Требует плановой миграции.",
                is_problematic=True,
                risk_level="medium",
                color_hex="#F59E0B",
            ),
            SoftwareCategory(
                id=3,
                name="Запрещенный к использованию",
                description="ПО, запрещённое политикой информационной безопасности компании (торренты, майнеры, P2P)",
                is_problematic=True,
                risk_level="critical",
                color_hex="#EF4444",
            ),
        ]
        for c in default_categories:
            db.add(c)
        await db.commit()

    # 2. Классификатор ПО (из файла data/Пример ПО.xlsx)
    cls_count = await db.execute(select(func.count(SoftwareClassifier.id)))
    if cls_count.scalar_one() == 0:
        await sync_software_classifiers(db)

    # 3. Единый реестр российского ПО (из data/Единый реестр российского ПО.xlsx)
    from sam.models.registry import RuSoftwareRegistry
    reg_count = await db.execute(select(func.count(RuSoftwareRegistry.id)))
    if reg_count.scalar_one() == 0:
        await sync_russian_registry(db, limit_rows=2000)

    # 4. База уязвимостей БДУ ФСТЭК (из data/уязвимости.xlsx или bdu.fstec.ru)
    try:
        vuln_count = (await db.execute(select(func.count(Vulnerability.id)))).scalar_one()
        if vuln_count == 0:
            await sync_vulnerabilities_from_file(db, limit_rows=5000)
    except Exception as e:
        print(f"Notice: initial vulnerability load error: {e}")

    # 5. Пересчёт алертов комплаенса
    await recalculate_compliance_alerts(db)
