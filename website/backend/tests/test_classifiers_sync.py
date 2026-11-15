import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from sam.services.registry_sync import sync_software_classifiers, OFFICIAL_SECTION_NAMES, fetch_classifiers_from_web
from sam.models.classifier import SoftwareClassifier


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


async def test_classifier_sync_from_registry():
    print("--- Testing sync_software_classifiers flow ---")
    db = AsyncMock()
    # Initially no existing classifiers
    db.execute.return_value = MockResult([])

    # In real files, rows 0-2 are header metadata, software rows start at index 3
    sample_registry_rows = [
        ["Дата:", "", "00:01:45 14.11.2026"],
        ["Реестр:", "", "Единый реестр российских программ..."],
        ["Регистрационный номер", "Наименование", "Альтернативные", "Класс ПО"],
        ["1", "ПО 1", "", "01.01 - BIOS и иное встроенное программное обеспечение (№621)"],
        ["2", "ПО 2", "", "01.01 - Встроенные системные программы: BIOS, UEFI и иные встроенные системные программы;\n03.11 - Средства защиты каналов передачи данных"],
        ["3", "ПО 3", "", "12.17 - Программное обеспечение для решения отраслевых задач в области образования"],
    ]

    with patch("sam.services.registry_sync.stream_xlsx_rows", return_value=iter(sample_registry_rows)):
        with patch("pathlib.Path.exists", return_value=True):
            with patch("sam.services.registry_sync.fetch_classifiers_from_web", return_value={}):
                with patch("sam.services.registry_sync._read_raw_sheet_rows", return_value=[]):
                    stats = await sync_software_classifiers(db)

                # Should have parsed 3 distinct codes: 01.01, 03.11, 12.17
                assert stats["total"] == 3
                assert stats["added"] == 3
                assert int(stats) == 3
                assert db.add.call_count == 3
                assert db.commit.called

                # Check added items args:
                added_codes = [call.args[0].code for call in db.add.call_args_list]
                assert "01.01" in added_codes
                assert "03.11" in added_codes
                assert "12.17" in added_codes

                # The 01.01 class should have preferred the modern non-(№621) name
                added_01 = [call.args[0] for call in db.add.call_args_list if call.args[0].code == "01.01"][0]
                assert "BIOS, UEFI" in added_01.class_name
                assert added_01.section_name == OFFICIAL_SECTION_NAMES["01"]

    print("PASS: sync_software_classifiers correctly parses, normalizes, and upserts classifiers.")


async def test_classifier_web_fallback_and_sections():
    print("--- Testing official section names coverage ---")
    assert len(OFFICIAL_SECTION_NAMES) == 12
    for sec_num in range(1, 13):
        code = f"{sec_num:02d}"
        assert code in OFFICIAL_SECTION_NAMES
        assert OFFICIAL_SECTION_NAMES[code].startswith(code)
    print("PASS: All 12 sections 01..12 are canonical.")


if __name__ == "__main__":
    asyncio.run(test_classifier_sync_from_registry())
    asyncio.run(test_classifier_web_fallback_and_sections())
