import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from sam.services.registry_sync import sync_russian_registry


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


async def test_sync_russian_registry_mocked():
    print("--- Testing sync_russian_registry flow ---")
    db = AsyncMock()
    # Mock existing reg numbers
    db.execute.return_value = MockResult([])

    # Mock stream_xlsx_rows to yield sample rows including multi-INN row from real data
    sample_rows = [
        ["Регистрационный номер", "Наименование", "Класс"],
        ["4285", "МойОфис Стандартный", "Офисные приложения", "01.01", "", "", "https://myoffice.ru", "", "", "", "", "Новые Облачные Технологии", "", "", "", "7701234567"],
        ["12345", "Astra Linux Special Edition", "Операционные системы", "01.02", "", "", "https://astralinux.ru", "", "", "", "", "ГК Астра", "", "", "", "7709876543"],
        ["35073", "Электронный лабораторный журнал", "LIMS", "09.03", "", "", "https://eln.irnitu.ru", "", "", "", "", "Российская Федерация;\nРоссийская Федерация", "", "", "", "1023801756120;\n1023801755779"],
    ]

    with patch("sam.services.registry_sync.stream_xlsx_rows", return_value=iter(sample_rows)):
        with patch("pathlib.Path.exists", return_value=True):
            added = await sync_russian_registry(db, limit_rows=3)
            assert added == 3
            assert db.add_all.called
            assert db.commit.called

    print("PASS: sync_russian_registry successfully parsed and batched records.")


if __name__ == "__main__":
    asyncio.run(test_sync_russian_registry_mocked())
