import os
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple, Optional
import requests
from sqlalchemy import select
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


async def sync_software_classifiers(db: AsyncSession) -> int:
    """
    Parses software sections and classes from data/Пример ПО.xlsx
    and populates software_classifiers table.
    """
    sample_file = settings.DATA_DIR / "Пример ПО.xlsx"
    if not sample_file.exists():
        sample_file = settings.BASE_DIR.parent.parent / "data" / "Пример ПО.xlsx"

    if not sample_file.exists():
        return 0

    rows = _read_raw_sheet_rows(str(sample_file))
    # Starting from row 3 (0-indexed) where real software data starts
    # Col 3: Section (e.g. '04 - Средства разработки программного обеспечения')
    # Col 4: Class (e.g. '04.03 - Библиотеки подпрограмм (SDK)')
    
    seen_classes: Dict[str, Dict[str, str]] = {}

    for r in rows:
        if len(r) >= 5:
            sec = r[3].strip()
            cls = r[4].strip()
            if not sec or not cls or sec == "Раздел" or sec == "5":
                continue
            
            # Extract section code
            sec_code = sec.split(" ")[0].split("-")[0].strip()
            cls_code = cls.split(" ")[0].split("-")[0].strip()
            
            if cls_code and cls_code not in seen_classes:
                seen_classes[cls_code] = {
                    "code": cls_code,
                    "section_code": sec_code,
                    "section_name": sec,
                    "class_name": cls,
                }

    added = 0
    for code, info in seen_classes.items():
        existing = await db.execute(
            select(SoftwareClassifier).where(SoftwareClassifier.code == code)
        )
        if not existing.scalar_one_or_none():
            db.add(SoftwareClassifier(**info))
            added += 1

    await db.commit()
    return added


async def sync_russian_registry(db: AsyncSession, limit_rows: Optional[int] = None) -> int:
    """
    Синхронизирует Единый реестр отечественного ПО.
    Загружает ВСЕ 31 986+ записей из Реестра без искусственного ограничения в 5000.
    Использует потоковый генератор stream_xlsx_rows и пакетную вставку.
    """
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
