import asyncio
import uuid
import time
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from sam.models.substitution import ImportSubstitution, SubstitutionCache
from sam.models.catalog import SoftwareCatalog
from sam.models.registry import RuSoftwareRegistry
from sam.services.substitution_service import (
    SubstitutionRateLimiter,
    is_official_software_name,
    check_is_in_ru_registry,
    get_cached_substitution_status,
    save_substitution_cache_record,
    process_software_substitution,
    enqueue_software_substitution_check,
    parse_substitution_html,
    _substitution_queue,
    _enqueued_names,
)


class MockResult:
    def __init__(self, item):
        self.item = item

    def scalar_one_or_none(self):
        return self.item

    def scalar_one(self):
        return self.item

    def scalars(self):
        m = MagicMock()
        m.all.return_value = self.item if isinstance(self.item, list) else [self.item]
        return m

    def all(self):
        return self.item if isinstance(self.item, list) else [self.item]


async def test_official_software_name_validation():
    print("--- 1. Testing is_official_software_name ---")
    # Official recognized names
    assert is_official_software_name("Adobe Photoshop 2024") is True
    assert is_official_software_name("Docker Desktop") is True
    assert is_official_software_name("Visual Studio Code") is True
    assert is_official_software_name("Google Chrome") is True
    assert is_official_software_name("1С:Предприятие 8") is True
    assert is_official_software_name("PostgreSQL") is True
    assert is_official_software_name("Notepad++") is True

    # Raw process / uncleaned binary names -> should be rejected
    assert is_official_software_name("photoshop.exe") is False
    assert is_official_software_name("setup.exe") is False
    assert is_official_software_name("unins000.exe") is False
    assert is_official_software_name("svchost.exe") is False
    assert is_official_software_name("cmd.exe") is False
    assert is_official_software_name("installer.msi") is False
    assert is_official_software_name("temp_file.tmp") is False
    assert is_official_software_name("") is False
    assert is_official_software_name("a") is False
    assert is_official_software_name("12345") is False

    print("PASS: Official software name validation works accurately.")


async def test_ru_registry_check():
    print("--- 2. Testing check_is_in_ru_registry ---")
    db = AsyncMock()

    # Case A: Software has ru_registry_id via catalog item
    cat_id = uuid.uuid4()
    db.execute.return_value = MockResult(4285)
    is_dom, reg_id = await check_is_in_ru_registry(db, "МойОфис Стандартный", catalog_software_id=cat_id)
    assert is_dom is True
    assert reg_id == 4285

    # Case B: Software matched by name in ru_software_registry table
    db.execute.return_value = MockResult(1234)
    is_dom, reg_id = await check_is_in_ru_registry(db, "Astra Linux")
    assert is_dom is True
    assert reg_id == 1234

    # Case C: Foreign software not in Russian registry
    db.execute.return_value = MockResult(None)
    is_dom, reg_id = await check_is_in_ru_registry(db, "Adobe Photoshop")
    assert is_dom is False
    assert reg_id is None

    print("PASS: Russian Software Registry check correctly distinguishes domestic vs foreign software.")


async def test_rate_limiter():
    print("--- 3. Testing SubstitutionRateLimiter (Anti-DDoS) ---")
    limiter = SubstitutionRateLimiter(min_interval=0.1)

    t0 = time.monotonic()
    await limiter.acquire()
    t1 = time.monotonic()
    await limiter.acquire()
    t2 = time.monotonic()

    # Second acquire must wait at least 0.1s
    assert (t2 - t1) >= 0.09, f"Rate limiter interval was too short: {t2 - t1}"

    # Backoff test
    limiter.trigger_backoff(delay=0.15)
    await limiter.acquire()
    t3 = time.monotonic()
    assert (t3 - t2) >= 0.14, f"Backoff delay was not applied: {t3 - t2}"

    print("PASS: Rate Limiter successfully throttles requests and applies backoff.")


async def test_caching_with_ttl():
    print("--- 4. Testing Substitution Cache with TTL ---")
    db = AsyncMock()

    now = datetime.now(timezone.utc)
    valid_cache = SubstitutionCache(
        software_name="Adobe Photoshop",
        has_substitution=True,
        substitutions_count=3,
        is_domestic=False,
        status="checked",
        last_checked_at=now,
        expires_at=now + timedelta(days=14),
    )

    # 1. Valid non-expired cache hit
    db.execute.return_value = MockResult(valid_cache)
    cached = await get_cached_substitution_status(db, "adobe photoshop")
    assert cached is not None
    assert cached.has_substitution is True
    assert cached.substitutions_count == 3

    # 2. Expired cache hit -> returns None
    expired_cache = SubstitutionCache(
        software_name="Old Tool",
        has_substitution=False,
        substitutions_count=0,
        is_domestic=False,
        status="not_found",
        last_checked_at=now - timedelta(days=20),
        expires_at=now - timedelta(days=6),
    )
    db.execute.return_value = MockResult(expired_cache)
    cached_exp = await get_cached_substitution_status(db, "Old Tool")
    assert cached_exp is None

    # 3. Saving cache record
    db.execute.return_value = MockResult(None)
    saved = await save_substitution_cache_record(
        db=db,
        software_name="Slack",
        has_substitution=False,
        substitutions_count=0,
        is_domestic=False,
        status="not_found",
        ttl_days=14,
    )
    assert saved.software_name == "Slack"
    assert saved.has_substitution is False
    assert saved.status == "not_found"
    assert saved.expires_at > now

    print("PASS: Substitution cache correctly respects TTL and avoids expired data.")


async def test_process_software_substitution_domestic():
    print("--- 5. Testing process_software_substitution for Domestic Software ---")
    db = AsyncMock()
    db.execute.return_value = MockResult(None)

    # Simulate finding in RuSoftwareRegistry
    with patch("sam.services.substitution_service.check_is_in_ru_registry", return_value=(True, 999)):
        res = await process_software_substitution(db, "МойОфис")
        assert res["status"] == "domestic"
        assert res["is_domestic"] is True
        assert res["has_substitution"] is False
        assert res["ru_registry_id"] == 999

    print("PASS: Domestic software bypasses external requests and registers status 'domestic'.")


async def test_process_software_substitution_foreign_with_caching():
    print("--- 6. Testing process_software_substitution for Foreign Software ---")
    db = AsyncMock()
    db.execute.return_value = MockResult(None)

    mock_html = """
    <div class="collection-item a-link" data-tab="registry" data-href="/registry/12345/">
        <div data-name="№ реестровой записи">12345</div>
        <div data-name="Наименование ПО">AliveColors</div>
        <div data-name="Правообладатель">АКВИС</div>
        <div data-name="Класс ПО" class="class-code">06.08</div>
        <div data-name="Класс ПО" class="class-item">Редакторы мультимедиа</div>
    </div>
    """

    with patch("sam.services.substitution_service.check_is_in_ru_registry", return_value=(False, None)):
        with patch("sam.services.substitution_service.get_cached_substitution_status", return_value=None):
            with patch("sam.services.substitution_service.fetch_live_substitution_rate_limited", return_value=mock_html):
                with patch("sam.services.substitution_service.save_substitution_items_to_db", return_value=1):
                    res = await process_software_substitution(db, "Adobe Photoshop")
                    assert res["status"] == "checked"
                    assert res["has_substitution"] is True
                    assert res["substitutions_count"] == 1
                    assert res["is_domestic"] is False

    print("PASS: Foreign software parses analogs, saves to DB, and creates cache record.")


async def test_queue_and_deduplication():
    print("--- 7. Testing enqueue_software_substitution_check deduplication ---")
    _enqueued_names.clear()
    while not _substitution_queue.empty():
        _substitution_queue.get_nowait()

    # First enqueue succeeds
    ok1 = enqueue_software_substitution_check("Figma")
    assert ok1 is True

    # Duplicate enqueue rejected
    ok2 = enqueue_software_substitution_check("figma")
    assert ok2 is False

    # Raw filename rejected
    ok3 = enqueue_software_substitution_check("figma.exe")
    assert ok3 is False

    assert _substitution_queue.qsize() == 1
    item = _substitution_queue.get_nowait()
    assert item[0] == "Figma"

    print("PASS: Queue deduplication and validation successfully prevented duplicate/invalid checks.")


async def test_save_substitution_items_long_class_and_owner():
    print("--- 8. Testing save_substitution_items_to_db with long class names and multi-codes ---")
    from sam.services.substitution_service import save_substitution_items_to_db

    db = AsyncMock()
    # Mock no existing substitution so it inserts
    db.execute.return_value = MockResult(None)

    long_class_name = (
        "Средства анализа исходного кода на закладки и уязвимости Серверное и связующее программное обеспечение "
        "Средства мониторинга и управления Среды разработки, тестирования и отладки Средства централизованного "
        "управления конечными устройствами Средства интеллектуального анализа данных (Data Mining) Средства поддержки принятия решений (DSS)"
    )
    long_class_code = "04.05 02.06 02.08 04.04 06.02 09.10 09.14 11.04 11.05"
    long_owner = "ОБЩЕСТВО С ОГРАНИЧЕННОЙ ОТВЕТСТВЕННОСТЬЮ \"НАУЧНО-ПРОИЗВОДСТВЕННОЕ ПРЕДПРИЯТИЕ ИНРИС-САФИБ\""

    items = [
        {
            "foreign_software_name": "AnyDesk",
            "russian_software_name": "Система удаленного мониторинга и управления «Ассистент» с динамическим анализатором программного кода «Дикод»",
            "russian_reg_number": "24668",
            "source": "registry",
            "owner_name": long_owner,
            "class_code": long_class_code,
            "class_name": long_class_name,
            "registration_date": "15.11.2024",
            "registry_url": "https://reestr.digital.gov.ru/reestr/2804326/",
        }
    ]

    added = await save_substitution_items_to_db(db, items)
    assert added == 1
    assert db.add.called
    added_obj = db.add.call_args[0][0]
    assert isinstance(added_obj, ImportSubstitution)
    assert added_obj.class_name == long_class_name
    assert added_obj.class_code == long_class_code
    assert added_obj.owner_name == long_owner
    assert db.commit.called

    print("PASS: Long class names and multi-code substitution records successfully processed without truncation errors.")


async def main():
    print("==================================================")
    print("Running Substitution Service & Rate Limiting Tests")
    print("==================================================")
    await test_official_software_name_validation()
    await test_ru_registry_check()
    await test_rate_limiter()
    await test_caching_with_ttl()
    await test_process_software_substitution_domestic()
    await test_process_software_substitution_foreign_with_caching()
    await test_queue_and_deduplication()
    await test_save_substitution_items_long_class_and_owner()
    print("==================================================")
    print("ALL SUBSTITUTION SERVICE TESTS PASSED SUCCESSFULLY!")
    print("==================================================")


if __name__ == "__main__":
    asyncio.run(main())
