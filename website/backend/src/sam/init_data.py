import os
import uuid
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sam.config import settings
from sam.models.category import SoftwareCategory
from sam.models.classifier import SoftwareClassifier
from sam.models.catalog import SoftwareCatalog
from sam.models.license import License
from sam.models.employee import Employee
from sam.models.computer import Computer
from sam.models.installed_software import InstalledSoftware
from sam.models.import_history import ImportHistory
from sam.services.registry_sync import sync_software_classifiers, sync_russian_registry
from sam.services.compliance_engine import recalculate_compliance_alerts
from sam.services.ai_matcher import match_raw_process_to_catalog
from sam.services.dump_parser import parse_dump_file


async def seed_database_if_empty(db: AsyncSession):
    # 1. Categories
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

    # 2. Classifiers
    cls_count = await db.execute(select(func.count(SoftwareClassifier.id)))
    if cls_count.scalar_one() == 0:
        await sync_software_classifiers(db)

    # 3. Russian Registry
    reg_count = await db.execute(select(func.count(RuSoftwareRegistry.id)))
    if reg_count.scalar_one() == 0:
        await sync_russian_registry(db, limit_rows=2000)

    # 4. Software Catalog (Whitelist)
    cat_items_count = await db.execute(select(func.count(SoftwareCatalog.id)))
    if cat_items_count.scalar_one() == 0:
        default_catalog = [
            SoftwareCatalog(
                id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
                name="Microsoft Office 2021 Professional Plus",
                vendor="Microsoft Corporation",
                description="Офисный пакет (Word, Excel, PowerPoint, Outlook) для корпоративных рабочих мест.",
                category_id=1,
                license_type="Commercial",
                max_installations=100,
                responsible_person="Иванов А.С. (ИТ)",
                approval_status="approved",
            ),
            SoftwareCatalog(
                id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
                name="Google Chrome",
                vendor="Google LLC",
                description="Корпоративный веб-браузер по умолчанию.",
                category_id=1,
                license_type="Open Source",
                max_installations=0,
                responsible_person="Иванов А.С. (ИТ)",
                approval_status="approved",
            ),
            SoftwareCatalog(
                id=uuid.UUID("00000000-0000-0000-0000-000000000003"),
                name="7-Zip",
                vendor="Igor Pavlov",
                description="Архиватор файлов с открытым исходным кодом.",
                category_id=1,
                license_type="Open Source",
                max_installations=0,
                responsible_person="Смирнов Е.В. (ИТ)",
                approval_status="approved",
            ),
            SoftwareCatalog(
                id=uuid.UUID("00000000-0000-0000-0000-000000000004"),
                name="Microsoft Visual Studio 2022 Professional",
                vendor="Microsoft Corporation",
                description="Интегрированная среда разработки для инженеров-программистов.",
                category_id=1,
                license_type="Commercial",
                max_installations=20,
                responsible_person="Кузнецов М.И. (Разработка)",
                approval_status="approved",
            ),
            SoftwareCatalog(
                id=uuid.UUID("00000000-0000-0000-0000-000000000005"),
                name="Telegram Desktop",
                vendor="Telegram FZ-LLC",
                description="Корпоративный мессенджер для оперативных коммуникаций.",
                category_id=1,
                license_type="Freeware",
                max_installations=0,
                responsible_person="Иванов А.С. (ИТ)",
                approval_status="approved",
            ),
            SoftwareCatalog(
                id=uuid.UUID("00000000-0000-0000-0000-000000000006"),
                name="1С:Предприятие 8",
                vendor="Фирма 1С",
                description="Платформа для автоматизации бухгалтерского и складского учёта.",
                category_id=1,
                license_type="Commercial",
                max_installations=50,
                responsible_person="Петрова Е.Н. (Бухгалтерия)",
                approval_status="approved",
            ),
            SoftwareCatalog(
                id=uuid.UUID("00000000-0000-0000-0000-000000000007"),
                name="BitTorrent / uTorrent Client",
                vendor="BitTorrent Inc.",
                description="P2P торрент-клиент. ЗАПРЕЩЁН политикой безопасности предприятия.",
                category_id=3,  # Запрещенный
                license_type="Freeware",
                max_installations=0,
                responsible_person="Служба ИБ",
                approval_status="rejected",
            ),
            SoftwareCatalog(
                id=uuid.UUID("00000000-0000-0000-0000-000000000008"),
                name="Oracle Java 8 Update 201",
                vendor="Oracle Corporation",
                description="Java Runtime Environment. Требует платной коммерческой подписки.",
                category_id=2,  # Устаревший
                license_type="Commercial",
                max_installations=10,
                responsible_person="Кузнецов М.И. (Разработка)",
                approval_status="approved",
            ),
        ]
        for item in default_catalog:
            db.add(item)
        await db.commit()

        # 5. Licenses for commercial products
        default_licenses = [
            License(
                software_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
                license_name="MS Office 2021 Pro Plus VL Volume License",
                license_type="Платный",
                license_model="per_device",
                total_purchased=100,
                unit_cost=Decimal("25000.00"),
                currency="RUB",
                valid_from=datetime.now(timezone.utc).date() - timedelta(days=365),
                valid_to=datetime.now(timezone.utc).date() + timedelta(days=730),
            ),
            License(
                software_id=uuid.UUID("00000000-0000-0000-0000-000000000004"),
                license_name="Visual Studio 2022 Professional Standalone",
                license_type="Платный",
                license_model="per_user",
                total_purchased=20,
                unit_cost=Decimal("45000.00"),
                currency="RUB",
                valid_from=datetime.now(timezone.utc).date() - timedelta(days=200),
                valid_to=datetime.now(timezone.utc).date() + timedelta(days=500),
            ),
            License(
                software_id=uuid.UUID("00000000-0000-0000-0000-000000000006"),
                license_name="1С:Предприятие 8 КОРП Клиентская лицензия на 50 р.м.",
                license_type="Платный",
                license_model="per_device",
                total_purchased=50,
                unit_cost=Decimal("32000.00"),
                currency="RUB",
                valid_from=datetime.now(timezone.utc).date() - timedelta(days=300),
                valid_to=datetime.now(timezone.utc).date() + timedelta(days=600),
            ),
            License(
                software_id=uuid.UUID("00000000-0000-0000-0000-000000000008"),
                license_name="Oracle Java SE Desktop Subscription",
                license_type="Платный",
                license_model="per_device",
                total_purchased=10,
                unit_cost=Decimal("18000.00"),
                currency="RUB",
                valid_from=datetime.now(timezone.utc).date() - timedelta(days=150),
                valid_to=datetime.now(timezone.utc).date() + timedelta(days=210),
            ),
        ]
        for lic in default_licenses:
            db.add(lic)
        await db.commit()

    # 6. Employees
    emp_count = await db.execute(select(func.count(Employee.id)))
    if emp_count.scalar_one() == 0:
        emp_sokolov_id = uuid.UUID("11111111-0000-0000-0000-000000000001")
        default_employees = [
            Employee(
                id=uuid.UUID("11111111-0000-0000-0000-000000000002"),
                full_name="Иванов Алексей Сергеевич",
                email="a.ivanov@company.ru",
                department="ИТ и Инфраструктура",
                position="Ведущий системный администратор",
                status="active",
            ),
            Employee(
                id=uuid.UUID("11111111-0000-0000-0000-000000000003"),
                full_name="Петрова Елена Николаевна",
                email="e.petrova@company.ru",
                department="Бухгалтерия",
                position="Главный бухгалтер",
                status="active",
            ),
            Employee(
                id=uuid.UUID("11111111-0000-0000-0000-000000000004"),
                full_name="Кузнецов Михаил Игоревич",
                email="m.kuznetsov@company.ru",
                department="Разработка ПО",
                position="Архитектор программных решений",
                status="active",
            ),
            Employee(
                id=emp_sokolov_id,
                full_name="Соколов Павел Васильевич",
                email="p.sokolov@company.ru",
                department="Маркетинг и Аналитика",
                position="Маркетолог (Уволен)",
                status="dismissed",  # Triggers zombie software alert
            ),
            Employee(
                id=uuid.UUID("11111111-0000-0000-0000-000000000005"),
                full_name="Михайлов Артем Игоревич",
                email="a.mikhailov@company.ru",
                department="Отдел логистики",
                position="Специалист по снабжению",
                status="active",
            ),
        ]
        for emp in default_employees:
            db.add(emp)
        await db.commit()

        # 7. Sample Computers
        default_computers = [
            Computer(
                id=uuid.UUID("22222222-0000-0000-0000-000000000001"),
                serial_number="G69ZD5J",
                hostname="WORKSTATION-IT-01",
                ip_address="192.168.1.15",
                mac_address="50:9A:4C:12:34:56",
                os_name="Windows 11 Pro",
                os_version="23H2",
                cpu_info="Intel Core i7-13700",
                ram_mb=32768,
                is_online=True,
                last_seen_at=datetime.now(timezone.utc),
                employee_id=uuid.UUID("11111111-0000-0000-0000-000000000002"),
            ),
            Computer(
                id=uuid.UUID("22222222-0000-0000-0000-000000000002"),
                serial_number="B1FG0S2",
                hostname="DEV-WORKSTATION-02",
                ip_address="192.168.1.42",
                mac_address="50:9A:4C:12:34:57",
                os_name="Windows 11 Pro",
                os_version="23H2",
                cpu_info="AMD Ryzen 9 7900X",
                ram_mb=65536,
                is_online=True,
                last_seen_at=datetime.now(timezone.utc),
                employee_id=uuid.UUID("11111111-0000-0000-0000-000000000004"),
            ),
            Computer(
                id=uuid.UUID("22222222-0000-0000-0000-000000000003"),
                serial_number="B1RG0S2",
                hostname="DISMISSED-PC-SOKOLOV",
                ip_address="192.168.1.99",
                mac_address="50:9A:4C:12:34:58",
                os_name="Windows 10 Pro",
                os_version="22H2",
                cpu_info="Intel Core i5-10400",
                ram_mb=16384,
                is_online=False,
                last_seen_at=datetime.now(timezone.utc) - timedelta(days=95),
                employee_id=emp_sokolov_id,  # Dismissed employee host
            ),
            Computer(
                id=uuid.UUID("22222222-0000-0000-0000-000000000004"),
                serial_number="SHADOW-PC-01",
                hostname="WORKSTATION-SHADOW",
                ip_address="192.168.10.105",
                mac_address="50:9A:4C:99:88:77",
                os_name="Windows 11 Pro",
                os_version="23H2",
                cpu_info="Intel Core i5-12400",
                ram_mb=16384,
                is_online=True,
                last_seen_at=datetime.now(timezone.utc),
                employee_id=uuid.UUID("11111111-0000-0000-0000-000000000005"),
            ),
        ]
        for comp in default_computers:
            db.add(comp)
        await db.commit()

        # 8. Sample installations creating realistic compliance triggers
        sample_installs = [
            # G69ZD5J: Chrome, 7-Zip, VS 2022
            InstalledSoftware(
                computer_id=uuid.UUID("22222222-0000-0000-0000-000000000001"),
                raw_display_name="Google Chrome",
                raw_publisher="Google LLC",
                raw_version="114.0.5735.199",
                catalog_software_id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
                category_id=1,
                match_confidence=0.99,
                is_verified_by_admin=True,
                last_launched_at=datetime.now(timezone.utc),
            ),
            InstalledSoftware(
                computer_id=uuid.UUID("22222222-0000-0000-0000-000000000001"),
                raw_display_name="7-Zip 19.00 (x64 edition)",
                raw_publisher="Igor Pavlov",
                raw_version="19.00.00.0",
                catalog_software_id=uuid.UUID("00000000-0000-0000-0000-000000000003"),
                category_id=1,
                match_confidence=0.98,
                is_verified_by_admin=True,
                last_launched_at=datetime.now(timezone.utc),
            ),
            InstalledSoftware(
                computer_id=uuid.UUID("22222222-0000-0000-0000-000000000001"),
                raw_display_name="Microsoft Office 2021",
                raw_publisher="Microsoft Corporation",
                raw_version="16.0.14326.20454",
                catalog_software_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
                category_id=1,
                match_confidence=0.95,
                is_verified_by_admin=True,
                last_launched_at=datetime.now(timezone.utc),
            ),
            # DISMISSED-PC: Has MS Office not launched for 95 days on a dismissed user's PC!
            InstalledSoftware(
                computer_id=uuid.UUID("22222222-0000-0000-0000-000000000003"),
                raw_display_name="Microsoft Office 2021 Professional Plus",
                raw_publisher="Microsoft Corporation",
                raw_version="16.0.14326.20454",
                catalog_software_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
                category_id=1,
                match_confidence=0.99,
                is_verified_by_admin=True,
                last_launched_at=datetime.now(timezone.utc) - timedelta(days=95),
            ),
            # WORKSTATION-SHADOW: Has prohibited uTorrent!
            InstalledSoftware(
                computer_id=uuid.UUID("22222222-0000-0000-0000-000000000004"),
                raw_display_name="uTorrent Web 1.2.8",
                raw_publisher="BitTorrent Inc.",
                raw_version="1.2.8.4900",
                catalog_software_id=uuid.UUID("00000000-0000-0000-0000-000000000007"),
                category_id=3,  # Запрещенный к использованию
                match_confidence=0.96,
                is_verified_by_admin=False,
                last_launched_at=datetime.now(timezone.utc),
            ),
        ]
        for inst in sample_installs:
            db.add(inst)
        await db.commit()

        # 9. Also seed from 'data/Пример дампа с компов.xlsx' to get realistic batch data
        dump_file = settings.DATA_DIR / "Пример дампа с компов.xlsx"
        if not dump_file.exists():
            dump_file = settings.BASE_DIR.parent.parent / "data" / "Пример дампа с компов.xlsx"

        if dump_file.exists():
            try:
                with open(dump_file, "rb") as fp:
                    dump_rows = parse_dump_file("Пример дампа с компов.xlsx", fp.read())
                    # Take first 300 rows to quickly seed multiple computers
                    computers_cache: Dict[str, Computer] = {}
                    all_existing_comps = (await db.execute(select(Computer))).scalars().all()
                    for c in all_existing_comps:
                        computers_cache[c.serial_number] = c

                    imported_installs = 0
                    for row in dump_rows[:250]:
                        sn = row.get("serial_number")
                        if not sn:
                            continue
                        if sn not in computers_cache:
                            new_c = Computer(
                                serial_number=sn,
                                hostname=f"HOST-{sn}",
                                ip_address=f"192.168.1.{100 + (len(computers_cache) % 150)}",
                                mac_address="50:9A:4C:" + ":".join(f"{b:02X}" for b in sn.encode()[:3]),
                                os_name="Windows 11 Pro",
                                os_version="23H2",
                                cpu_info="Intel Core i5-11400",
                                ram_mb=16384,
                                is_online=True,
                                last_seen_at=datetime.now(timezone.utc),
                            )
                            db.add(new_c)
                            await db.flush()
                            computers_cache[sn] = new_c

                        comp = computers_cache[sn]
                        display_name = row.get("display_name", "")
                        publisher = row.get("publisher", "")
                        version = row.get("version", "")

                        match_res = await match_raw_process_to_catalog(db, display_name, publisher)
                        cat_id = match_res.get("matched_catalog_software_id")
                        category_id = match_res.get("category_id") or 1

                        inst_obj = InstalledSoftware(
                            computer_id=comp.id,
                            raw_display_name=display_name,
                            raw_publisher=publisher,
                            raw_version=version,
                            catalog_software_id=uuid.UUID(cat_id) if cat_id else None,
                            category_id=category_id,
                            match_confidence=match_res.get("confidence", 0.0),
                            is_verified_by_admin=match_res.get("confidence", 0.0) >= 0.90,
                            last_launched_at=datetime.now(timezone.utc),
                            source="automatic",
                        )
                        db.add(inst_obj)
                        imported_installs += 1

                    db.add(
                        ImportHistory(
                            filename="Пример дампа с компов.xlsx",
                            total_rows=len(dump_rows),
                            computers_affected=len(computers_cache),
                            software_rows_imported=imported_installs,
                            matched_automatically=imported_installs,
                            status="success",
                        )
                    )
                    await db.commit()
            except Exception as e:
                print(f"Notice: initial dump load error: {e}")

    # 10. Run initial compliance recalculation
    await recalculate_compliance_alerts(db)
