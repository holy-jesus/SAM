import os
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple, Optional
import requests
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sam.config import settings
from sam.models.classifier import SoftwareClassifier
from sam.models.registry import RuSoftwareRegistry


def stream_xlsx_rows(file_path_or_bytes: Any):
    """
    Потоковый генератор строк из XLSX файла с использованием iterparse.
    Работает быстро (1-2 сек на 35 000 строк) и с минимальным потреблением памяти.
    """
    if isinstance(file_path_or_bytes, (str, os.PathLike)):
        if not os.path.exists(file_path_or_bytes):
            return
        z = zipfile.ZipFile(file_path_or_bytes, "r")
    else:
        import io
        z = zipfile.ZipFile(io.BytesIO(file_path_or_bytes), "r")

    try:
        sst: List[str] = []
        if "xl/sharedStrings.xml" in z.namelist():
            with z.open("xl/sharedStrings.xml") as f:
                for event, elem in ET.iterparse(f):
                    if elem.tag.endswith("si"):
                        sst.append("".join(elem.itertext()))
                        elem.clear()

        sheet_filename = "xl/worksheets/sheet1.xml"
        if sheet_filename not in z.namelist():
            for name in z.namelist():
                if name.startswith("xl/worksheets/sheet") and name.endswith(".xml"):
                    sheet_filename = name
                    break

        with z.open(sheet_filename) as f:
            for event, elem in ET.iterparse(f):
                if elem.tag.endswith("row"):
                    row_vals: List[str] = []
                    for c in elem.findall("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c"):
                        v = c.find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v")
                        t = c.attrib.get("t")
                        val = v.text if v is not None else ""
                        if t == "s" and val.isdigit() and int(val) < len(sst):
                            val = sst[int(val)]
                        elif t == "inlineStr":
                            it = c.find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}is/{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")
                            if it is not None and it.text:
                                val = it.text
                        row_vals.append(val.strip())
                    if any(row_vals):
                        yield row_vals
                    elem.clear()
    finally:
        z.close()


def _read_raw_sheet_rows(file_path: str, max_rows: int = 100000) -> List[List[str]]:
    """Обратная совместимость: возвращает список строк."""
    rows = []
    for r in stream_xlsx_rows(file_path):
        rows.append(r)
        if len(rows) >= max_rows:
            break
    return rows


OFFICIAL_SECTION_NAMES = {
    "01": "01 - Встроенное программное обеспечение",
    "02": "02 - Системное программное обеспечение",
    "03": "03 - Средства обеспечения информационной безопасности",
    "04": "04 - Средства разработки программного обеспечения",
    "05": "05 - Пользовательское прикладное программное обеспечение",
    "06": "06 - Офисное и коммуникационное программное обеспечение",
    "07": "07 - Средства обработки, анализа и распознавания данных",
    "08": "08 - Промышленное программное обеспечение",
    "09": "09 - Программное обеспечение для управления процессами предприятия",
    "10": "10 - Обработка больших данных и моделирование",
    "11": "11 - Средства искусственного интеллекта и аналитики",
    "12": "12 - Программное обеспечение для решения отраслевых задач",
}


async def fetch_classifiers_from_web() -> Dict[str, Dict[str, str]]:
    """
    Попытка загрузки актуального справочника классов с портала ru-ikt.ru/reestrpo.
    При сетевых ограничениях или ошибках подключения возвращает пустой словарь (срабатывает локальный реестр).
    """
    url = "https://ru-ikt.ru/reestrpo"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    web_items: Dict[str, Dict[str, str]] = {}
    try:
        import httpx
        import re
        async with httpx.AsyncClient(timeout=4.0, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200 and resp.text:
                pattern = re.compile(r'(\d{2}\.\d{2})\s*[-–—]\s*([^<"\r\n]+)')
                for match in pattern.finditer(resp.text):
                    code = match.group(1).strip()
                    title = match.group(2).strip()
                    sec_code = code.split('.')[0]
                    sec_name = OFFICIAL_SECTION_NAMES.get(sec_code, f"{sec_code} - Раздел {sec_code}")
                    web_items[code] = {
                        "code": code,
                        "section_code": sec_code,
                        "section_name": sec_name,
                        "class_name": f"{code} - {title}",
                    }
    except Exception:
        # Сеть недоступна или таймаут — продолжаем работу с локальным реестром
        pass
    return web_items


class ClassifierSyncResult(dict):
    """Словарь результатов синхронизации с поддержкой неявного int для обратной совместимости."""
    def __int__(self):
        return self.get("added", 0)

    def __index__(self):
        return self.get("added", 0)


async def sync_software_classifiers(db: AsyncSession) -> Dict[str, Any]:
    """
    Синхронизирует полный официальный классификатор ПО РФ:
    1. Пробует подтянуть актуальные данные с https://ru-ikt.ru/reestrpo
    2. Извлекает полный реестр классов из data/Единый реестр российского ПО.xlsx (12 разделов, 159+ классов)
    3. Дополняет классами из data/Пример ПО.xlsx при наличии
    4. Выполняет upsert в таблицу software_classifiers
    """
    import re
    seen_classes: Dict[str, Dict[str, str]] = {}
    sources: List[str] = []

    # 1. Онлайн-источник ru-ikt.ru
    web_classes = await fetch_classifiers_from_web()
    if web_classes:
        seen_classes.update(web_classes)
        sources.append("https://ru-ikt.ru/reestrpo")

    # 2. Основной надежный источник: Единый реестр российского ПО.xlsx
    excel_path = settings.DATA_DIR / "Единый реестр российского ПО.xlsx"
    if not excel_path.exists():
        excel_path = settings.BASE_DIR.parent.parent / "data" / "Единый реестр российского ПО.xlsx"

    if excel_path.exists():
        sources.append("data/Единый реестр российского ПО.xlsx")
        pattern = re.compile(r'^(\d{2})\.(\d{2})\s*[-–—]?\s*(.*)$')
        for i, row in enumerate(stream_xlsx_rows(str(excel_path))):
            if i < 3 or len(row) <= 3:
                continue
            val = row[3]
            if not val:
                continue
            for item in val.replace('\r', '\n').split('\n'):
                for sub in item.split(';'):
                    c = sub.strip()
                    m = pattern.match(c)
                    if not m:
                        continue
                    sec_code = m.group(1)
                    sub_code = m.group(2)
                    code = f"{sec_code}.{sub_code}"

                    # Предпочитаем современные наименования (без пометки устаревшего №621)
                    if code in seen_classes:
                        if "(№621)" in seen_classes[code]["class_name"] and "(№621)" not in c:
                            seen_classes[code]["class_name"] = c
                    else:
                        sec_name = OFFICIAL_SECTION_NAMES.get(sec_code, f"{sec_code} - Раздел {sec_code}")
                        seen_classes[code] = {
                            "code": code,
                            "section_code": sec_code,
                            "section_name": sec_name,
                            "class_name": c,
                        }

    # 3. Дополнительный источник: data/Пример ПО.xlsx
    sample_file = settings.DATA_DIR / "Пример ПО.xlsx"
    if not sample_file.exists():
        sample_file = settings.BASE_DIR.parent.parent / "data" / "Пример ПО.xlsx"

    if sample_file.exists():
        sources.append("data/Пример ПО.xlsx")
        pattern = re.compile(r'^(\d{2})\.(\d{2})\s*[-–—]?\s*(.*)$')
        for r in _read_raw_sheet_rows(str(sample_file)):
            if len(r) >= 5:
                sec = r[3].strip()
                cls = r[4].strip()
                if not sec or not cls or sec == "Раздел" or sec == "5":
                    continue
                m = pattern.match(cls)
                if m:
                    sec_code = m.group(1)
                    code = f"{sec_code}.{m.group(2)}"
                    if code not in seen_classes:
                        sec_name = OFFICIAL_SECTION_NAMES.get(sec_code, sec)
                        seen_classes[code] = {
                            "code": code,
                            "section_code": sec_code,
                            "section_name": sec_name,
                            "class_name": cls,
                        }

    # 4. Upsert в БД
    existing_result = await db.execute(select(SoftwareClassifier))
    existing_map = {c.code: c for c in existing_result.scalars().all()}

    added = 0
    updated = 0
    for code, info in seen_classes.items():
        if code in existing_map:
            obj = existing_map[code]
            changed = False
            if obj.class_name != info["class_name"] and "(№621)" not in info["class_name"]:
                obj.class_name = info["class_name"]
                changed = True
            if obj.section_name != info["section_name"]:
                obj.section_name = info["section_name"]
                changed = True
            if changed:
                updated += 1
        else:
            db.add(SoftwareClassifier(**info))
            added += 1

    await db.commit()
    return ClassifierSyncResult({
        "total": len(seen_classes),
        "added": added,
        "updated": updated,
        "sources": sources,
    })


async def sync_russian_registry(db: AsyncSession, limit_rows: Optional[int] = None) -> int:
    """
    Синхронизирует Единый реестр отечественного ПО.
    Загружает ВСЕ 31 986+ записей из Реестра без искусственного ограничения в 5000.
    Использует потоковый генератор stream_xlsx_rows и пакетную вставку.
    """
    # 0. Автоматическая самодиагностика: приведение типа embedding к vector(1536) при необходимости
    try:
        await db.execute(text("""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'ru_software_registry' AND column_name = 'embedding' AND data_type = 'ARRAY'
                ) THEN
                    ALTER TABLE ru_software_registry 
                    ALTER COLUMN embedding TYPE vector(1536) 
                    USING CASE 
                        WHEN embedding IS NULL THEN NULL 
                        ELSE (replace(replace(embedding::text, '{', '['), '}', ']')::vector) 
                    END;
                END IF;

                -- Расширение колонок ru_software_registry для предотвращения ошибки value too long
                ALTER TABLE ru_software_registry ALTER COLUMN vendor_inn TYPE TEXT;
                ALTER TABLE ru_software_registry ALTER COLUMN vendor_name TYPE TEXT;
                ALTER TABLE ru_software_registry ALTER COLUMN name TYPE TEXT;
                ALTER TABLE ru_software_registry ALTER COLUMN reg_number TYPE VARCHAR(100);
            END $$;
        """))
        await db.commit()
    except Exception as e:
        print(f"Notice: ru_software_registry embedding column type check: {e}")

    data_file = settings.DATA_DIR / "Единый реестр российского ПО.xlsx"
    if not data_file.exists():
        data_file = settings.DATA_DIR / "Единый реестр Российского ПО.xlsx"
    if not data_file.exists():
        data_file = settings.BASE_DIR.parent.parent / "data" / "Единый реестр российского ПО.xlsx"

    # Попытка скачать свежий список онлайн, если доступна сеть
    source: Any = None
    url = "https://reestr.digital.gov.ru/reestr/?export=list"
    try:
        resp = requests.get(url, timeout=4)
        if resp.status_code == 200 and len(resp.content) > 1000:
            source = resp.content
    except Exception:
        pass

    if source is None and data_file.exists():
        source = str(data_file)

    if not source:
        return 0

    # Предзагрузка существующих рег. номеров в память для ускорения проверки
    existing_reg_res = await db.execute(select(RuSoftwareRegistry.reg_number))
    existing_reg_nums = set(existing_reg_res.scalars().all())

    records_added = 0
    batch: List[RuSoftwareRegistry] = []
    header_found = False

    for r in stream_xlsx_rows(source):
        if len(r) > 1 and "Регистрационный" in r[0]:
            header_found = True
            continue

        if not header_found:
            continue

        if len(r) < 2 or not r[0].strip() or not r[1].strip():
            continue

        reg_num = r[0].strip()
        if reg_num in existing_reg_nums:
            continue

        name = r[1].strip()
        alt_names = r[2].strip() if len(r) > 2 else ""
        sw_class = r[3].strip() if len(r) > 3 else ""
        doc_url = r[6].strip() if len(r) > 6 else ""
        vendor_name = r[11].strip() if len(r) > 11 else ""
        vendor_inn = r[15].strip() if len(r) > 15 else ""

        is_ai = "искусственн" in (name + " " + alt_names + " " + sw_class).lower()
        batch.append(
            RuSoftwareRegistry(
                reg_number=reg_num,
                name=name,
                alternative_names=alt_names or None,
                software_class=sw_class or None,
                vendor_name=vendor_name or None,
                vendor_inn=vendor_inn or None,
                documentation_url=doc_url or None,
                is_ai=is_ai,
            )
        )
        existing_reg_nums.add(reg_num)
        records_added += 1

        if len(batch) >= 1000:
            db.add_all(batch)
            await db.commit()
            batch = []

        if limit_rows is not None and records_added >= limit_rows:
            break

    if batch:
        db.add_all(batch)
        await db.commit()

    return records_added


async def generate_registry_embeddings_batch(db: AsyncSession, limit: int = 200) -> int:
    """
    Генерирует и сохраняет векторные эмбеддинги для записей ru_software_registry через OpenAI API.
    """
    stmt = (
        select(RuSoftwareRegistry)
        .where(RuSoftwareRegistry.embedding.is_null())
        .limit(limit)
    )
    result = await db.execute(stmt)
    records = list(result.scalars().all())
    if not records or not settings.OPENAI_API_KEY:
        return 0

    try:
        from openai import AsyncOpenAI
        client_kwargs = {"api_key": settings.OPENAI_API_KEY}
        if settings.OPENAI_BASE_URL:
            client_kwargs["base_url"] = settings.OPENAI_BASE_URL
        client = AsyncOpenAI(**client_kwargs)

        texts = [f"{r.name} {r.alternative_names or ''} {r.software_class or ''}" for r in records]
        updated = 0
        for i in range(0, len(texts), 50):
            sub_texts = texts[i:i + 50]
            sub_records = records[i:i + 50]
            resp = await client.embeddings.create(
                model=settings.OPENAI_EMBEDDING_MODEL or "text-embedding-3-small",
                input=sub_texts
            )
            for rec, emb_data in zip(sub_records, resp.data):
                rec.embedding = emb_data.embedding
                updated += 1
            await db.commit()
        return updated
    except Exception as e:
        print(f"Notice: generating registry embeddings failed: {e}")
        return 0
