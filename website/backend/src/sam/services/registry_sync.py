import os
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple
import requests
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sam.config import settings
from sam.models.classifier import SoftwareClassifier
from sam.models.registry import RuSoftwareRegistry


def _read_raw_sheet_rows(file_path: str, max_rows: int = 100000) -> List[List[str]]:
    if not os.path.exists(file_path):
        return []

    with zipfile.ZipFile(file_path, "r") as z:
        sst: List[str] = []
        if "xl/sharedStrings.xml" in z.namelist():
            tree = ET.fromstring(z.read("xl/sharedStrings.xml"))
            ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
            for si in tree.findall(f"{ns}si"):
                text = "".join([t.text or "" for t in si.iter(f"{ns}t")])
                sst.append(text)

        sheet_filename = "xl/worksheets/sheet1.xml"
        if sheet_filename not in z.namelist():
            for name in z.namelist():
                if name.startswith("xl/worksheets/sheet") and name.endswith(".xml"):
                    sheet_filename = name
                    break

        sheet_xml = z.read(sheet_filename)
        stree = ET.fromstring(sheet_xml)
        ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
        rows: List[List[str]] = []

        for r in stree.findall(f".//{ns}row"):
            row_vals: List[str] = []
            for c in r.findall(f"{ns}c"):
                v = c.find(f"{ns}v")
                val = v.text if v is not None else ""
                t = c.attrib.get("t")
                if t == "s" and val.isdigit() and int(val) < len(sst):
                    val = sst[int(val)]
                elif t == "inlineStr":
                    it = c.find(f"{ns}is/{ns}t")
                    if it is not None and it.text:
                        val = it.text
                row_vals.append(val.strip())
            if any(row_vals):
                rows.append(row_vals)
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


async def sync_russian_registry(db: AsyncSession, limit_rows: int = 5000) -> int:
    """
    Syncs Russian Software Registry. Attempts web download first,
    falls back to data/Единый реестр российского ПО.xlsx.
    """
    data_file = settings.DATA_DIR / "Единый реестр российского ПО.xlsx"
    if not data_file.exists():
        data_file = settings.DATA_DIR / "Единый реестр Российского ПО.xlsx"
    if not data_file.exists():
        data_file = settings.BASE_DIR.parent.parent / "data" / "Единый реестр российского ПО.xlsx"

    # Try web download if possible
    url = "https://reestr.digital.gov.ru/reestr/?export=list"
    content_bytes = None
    try:
        resp = requests.get(url, timeout=4)
        if resp.status_code == 200 and len(resp.content) > 1000:
            content_bytes = resp.content
    except Exception:
        pass

    rows: List[List[str]] = []
    if content_bytes:
        import io
        with zipfile.ZipFile(io.BytesIO(content_bytes)) as z:
            pass  # If downloaded directly
    elif data_file.exists():
        rows = _read_raw_sheet_rows(str(data_file), max_rows=limit_rows)

    if not rows:
        return 0

    # Header is at row index 2:
    # Col 0: Регистрационный номер
    # Col 1: Наименование ПО
    # Col 2: Альтернативные названия ПО
    # Col 3: Класс ПО
    # Col 4: Код продукции
    # Col 5: Дата исключения
    # Col 6: Сайт с документацией
    header_idx = -1
    for idx, r in enumerate(rows[:5]):
        if len(r) > 1 and "Регистрационный" in r[0]:
            header_idx = idx
            break

    if header_idx == -1:
        header_idx = 2

    records_added = 0
    batch: List[RuSoftwareRegistry] = []

    for r in rows[header_idx + 1:]:
        if len(r) < 2 or not r[0].strip() or not r[1].strip():
            continue

        reg_num = r[0].strip()
        name = r[1].strip()
        alt_names = r[2].strip() if len(r) > 2 else ""
        sw_class = r[3].strip() if len(r) > 3 else ""
        doc_url = r[6].strip() if len(r) > 6 else ""

        # Check existing
        existing = await db.execute(
            select(RuSoftwareRegistry).where(RuSoftwareRegistry.reg_number == reg_num)
        )
        if not existing.scalar_one_or_none():
            is_ai = "искусственн" in (name + " " + alt_names + " " + sw_class).lower()
            batch.append(
                RuSoftwareRegistry(
                    reg_number=reg_num,
                    name=name,
                    alternative_names=alt_names,
                    software_class=sw_class,
                    documentation_url=doc_url,
                    is_ai=is_ai,
                )
            )
            records_added += 1

        if len(batch) >= 200:
            for item in batch:
                db.add(item)
            await db.commit()
            batch = []

    if batch:
        for item in batch:
            db.add(item)
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
