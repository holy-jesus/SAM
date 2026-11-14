import re
import json
import math
import uuid
import difflib
import asyncio
from typing import Optional, Dict, Any, List, Tuple
import urllib.parse
import urllib.request

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from sam.config import settings
from sam.models.catalog import SoftwareCatalog
from sam.models.installed_software import InstalledSoftware
from sam.models.registry import RuSoftwareRegistry
from sam.models.process_signature import ProcessSignature


def clean_process_name(raw_name: str) -> str:
    cleaned = raw_name.strip()
    cleaned = re.sub(r"\.(exe|msi|bin|app|dmg|zip)$", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace("_", " ").replace("-", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def compute_string_similarity(s1: str, s2: str) -> float:
    s1_low = s1.lower()
    s2_low = s2.lower()
    if s1_low == s2_low:
        return 1.0

    tokens1 = set(re.findall(r"\w+", s1_low))
    tokens2 = set(re.findall(r"\w+", s2_low))
    if not tokens1 or not tokens2:
        return 0.0

    jaccard = len(tokens1 & tokens2) / len(tokens1 | tokens2)
    seq = difflib.SequenceMatcher(None, s1_low, s2_low).ratio()
    return max(jaccard, seq)


def compute_cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0
    dot = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return max(0.0, min(1.0, dot / (norm1 * norm2)))


# ==========================================
# Вспомогательные структуры для поиска по путям и файлам
# ==========================================
GENERIC_EXECUTABLES = {
    "setup.exe", "install.exe", "installer.exe", "uninstall.exe", "unins000.exe",
    "uninst.exe", "update.exe", "updater.exe", "patch.exe", "helper.exe",
    "service.exe", "agent.exe", "host.exe", "client.exe", "server.exe",
    "start.exe", "run.exe", "app.exe", "main.exe", "cli.exe"
}


def extract_path_components(path: Optional[str], raw_name: str) -> Tuple[str, str, str]:
    """
    Разбирает путь на:
    - exe_name: имя исполняемого файла (например, 'chrome.exe' или 'pycharm64.exe')
    - app_dir: имя ключевой папки приложения (например, 'chrome', 'pycharm 2023.2', '1cv8')
    - norm_path: очищенный путь в нижнем регистре со стандартными прямыми слэшами
    """
    if not path or not path.strip():
        name_clean = raw_name.strip()
        exe = name_clean.split("/")[-1].split("\\")[-1].lower()
        if not exe.endswith((".exe", ".msi", ".bin", ".app")):
            exe = f"{exe}.exe"
        return exe, "", ""

    norm = path.replace("\\", "/").strip().lower().strip("\"' ")
    parts = [p for p in norm.split("/") if p]
    if not parts:
        return "", "", ""

    exe_name = parts[-1]
    if "." not in exe_name and raw_name.lower().endswith(".exe"):
        exe_name = raw_name.lower()

    skip_dirs = {
        "bin", "application", "app", "x86_64", "x64", "win64", "win32",
        "client", "root", "program files", "program files (x86)",
        "appdata", "local", "roaming", "opt", "usr", "etc"
    }
    app_dir = ""
    for p in reversed(parts[:-1]):
        if p in skip_dirs or re.match(r"^v?\d+(\.\d+)*$", p) or re.match(r"^office\d*$", p):
            continue
        app_dir = p
        break

    return exe_name, app_dir, norm


# ==========================================
# Генерация эмбеддингов через OpenAI API
# ==========================================
async def generate_embedding(text_content: str) -> Optional[List[float]]:
    if not settings.OPENAI_API_KEY or not text_content.strip():
        return None

    try:
        from openai import AsyncOpenAI
        client_kwargs: Dict[str, Any] = {"api_key": settings.OPENAI_API_KEY}
        if settings.OPENAI_BASE_URL:
            client_kwargs["base_url"] = settings.OPENAI_BASE_URL

        client = AsyncOpenAI(**client_kwargs)
        resp = await asyncio.wait_for(
            client.embeddings.create(
                model=settings.OPENAI_EMBEDDING_MODEL or "text-embedding-3-small",
                input=text_content.strip()
            ),
            timeout=5.0
        )
        return resp.data[0].embedding
    except Exception as e:
        print(f"Notice: OpenAI embedding generation skipped/failed: {e}")
        return None


def _find_catalog_item_by_name(catalog_items: List[SoftwareCatalog], query_name: str) -> Optional[SoftwareCatalog]:
    q_low = query_name.lower()
    best_item = None
    best_score = 0.0

    for item in catalog_items:
        i_low = item.name.lower()
        if q_low == i_low or q_low in i_low or i_low in q_low:
            return item
        score = compute_string_similarity(query_name, item.name)
        if score > best_score:
            best_score = score
            best_item = item

    if best_item and best_score >= 0.45:
        return best_item
    return None


# ==========================================
# Сохранение в БД: Самообучение системы
# ==========================================
async def save_learned_signature(
    db: AsyncSession,
    process_name: str,
    normalized_name: str,
    binary_hash: Optional[str],
    catalog_software_id: Optional[uuid.UUID],
    ru_registry_id: Optional[int],
    vendor: Optional[str],
    confidence: float,
    match_source: str,
    embedding: Optional[List[float]] = None,
) -> ProcessSignature:
    """
    Записывает результат распознавания в базу данных (process_signatures),
    чтобы в будущем мгновенно находить процесс по хэшу, имени или векторному сходству.
    """
    # Проверяем, существует ли уже такая сигнатура
    stmt = select(ProcessSignature).where(
        or_(
            func.lower(ProcessSignature.process_name) == process_name.lower(),
            and_(
                binary_hash is not None,
                ProcessSignature.binary_hash == binary_hash
            )
        )
    )
    existing_res = await db.execute(stmt)
    existing = existing_res.scalar_one_or_none()

    if existing:
        existing.times_matched += 1
        if catalog_software_id and not existing.catalog_software_id:
            existing.catalog_software_id = catalog_software_id
        if ru_registry_id and not existing.ru_registry_id:
            existing.ru_registry_id = ru_registry_id
        if vendor and not existing.vendor:
            existing.vendor = vendor
        if embedding and not existing.embedding:
            existing.embedding = embedding
        existing.confidence = max(existing.confidence, confidence)
        await db.commit()
        return existing

    # Генерируем эмбеддинг, если его нет
    if not embedding and settings.OPENAI_API_KEY:
        embedding = await generate_embedding(f"{process_name} {normalized_name} {vendor or ''}")

    sig = ProcessSignature(
        process_name=process_name,
        normalized_name=normalized_name,
        binary_hash=binary_hash,
        catalog_software_id=catalog_software_id,
        ru_registry_id=ru_registry_id,
        vendor=vendor,
        confidence=confidence,
        match_source=match_source,
        embedding=embedding,
        times_matched=1,
    )
    db.add(sig)
    await db.commit()
    await db.refresh(sig)
    return sig


# ==========================================
# Шаг 1: Поиск по хэшу файла в БД
# ==========================================
async def match_by_hash(
    db: AsyncSession,
    binary_hash: Optional[str],
    catalog_items: List[SoftwareCatalog]
) -> Optional[Dict[str, Any]]:
    if not binary_hash or not binary_hash.strip():
        return None

    hash_clean = binary_hash.strip().lower()

    # 1.1 Поиск в таблице process_signatures
    sig_stmt = (
        select(ProcessSignature)
        .where(func.lower(ProcessSignature.binary_hash) == hash_clean)
        .limit(1)
    )
    sig_res = await db.execute(sig_stmt)
    sig = sig_res.scalar_one_or_none()
    if sig:
        sig.times_matched += 1
        await db.commit()
        cat_sw = sig.catalog_software
        return {
            "matched_catalog_software_id": str(sig.catalog_software_id) if sig.catalog_software_id else None,
            "matched_name": cat_sw.name if cat_sw else sig.normalized_name,
            "vendor": cat_sw.vendor if cat_sw else sig.vendor,
            "category_id": cat_sw.category_id if cat_sw else 1,
            "confidence": 1.0,
            "match_source": "hash",
            "reasoning": f"Точное совпадение по хэшу файла ({hash_clean[:12]}...) в базе знаний сигнатур.",
        }

    # 1.2 Поиск в таблице installed_software по ранее проверенным файлам
    stmt = (
        select(InstalledSoftware)
        .where(
            and_(
                func.lower(InstalledSoftware.binary_hash) == hash_clean,
                InstalledSoftware.catalog_software_id.is_not(None)
            )
        )
        .limit(1)
    )
    res = await db.execute(stmt)
    inst = res.scalar_one_or_none()
    if inst and inst.catalog_software:
        # Сохраняем в process_signatures для ускорения будущих поисков
        await save_learned_signature(
            db=db,
            process_name=inst.raw_display_name,
            normalized_name=inst.catalog_software.name,
            binary_hash=hash_clean,
            catalog_software_id=inst.catalog_software.id,
            ru_registry_id=inst.catalog_software.ru_registry_id,
            vendor=inst.catalog_software.vendor,
            confidence=1.0,
            match_source="hash",
        )
        return {
            "matched_catalog_software_id": str(inst.catalog_software.id),
            "matched_name": inst.catalog_software.name,
            "vendor": inst.catalog_software.vendor,
            "category_id": inst.catalog_software.category_id,
            "confidence": 1.0,
            "match_source": "hash",
            "reasoning": f"Точное совпадение по хэшу файла ({hash_clean[:12]}...) с проверенным ПО '{inst.catalog_software.name}'.",
        }

    return None


# ==========================================
# Шаг 2: Эвристический поиск по БД (Путь установки + Имя .exe + Издатель)
# Сохраняет точное ПО из каталога, но фиксирует новую реальную версию (reported_version)
# ==========================================
async def match_by_path_and_executable(
    db: AsyncSession,
    raw_process_name: str,
    install_path: Optional[str],
    reported_version: Optional[str],
    publisher: Optional[str],
    catalog_items: List[SoftwareCatalog],
    binary_hash: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Эвристический поиск по БД по пути установки, имени исполняемого файла и издателю.
    Решает проблему минорных обновлений версий ПО (когда хэш изменился, но путь и .exe те же).
    При успешном сопоставлении фиксирует фактическую переданную версию (reported_version),
    а новый хэш записывает в process_signatures, самообучая систему.
    """
    exe_name, app_dir, norm_path = extract_path_components(install_path, raw_process_name)
    if not exe_name and not norm_path:
        return None

    clean_name = clean_process_name(raw_process_name).lower()
    is_generic = exe_name in GENERIC_EXECUTABLES

    # 1. Поиск среди ранее проверенных записей InstalledSoftware в БД
    query_conditions = []
    if exe_name and not is_generic:
        query_conditions.append(func.lower(InstalledSoftware.install_path).ilike(f"%{exe_name}"))
    if app_dir:
        query_conditions.append(func.lower(InstalledSoftware.install_path).ilike(f"%{app_dir}%"))
    if clean_name and len(clean_name) >= 3:
        query_conditions.append(func.lower(InstalledSoftware.raw_display_name).ilike(f"%{clean_name}%"))

    best_match_cat = None
    best_score = 0.0

    if query_conditions:
        stmt = (
            select(InstalledSoftware)
            .where(
                and_(
                    InstalledSoftware.catalog_software_id.is_not(None),
                    or_(*query_conditions)
                )
            )
            .order_by(InstalledSoftware.is_verified_by_admin.desc(), InstalledSoftware.match_confidence.desc())
            .limit(30)
        )
        res = await db.execute(stmt)
        candidates = res.scalars().all()

        for cand in candidates:
            cand_cat = getattr(cand, "catalog_software", None)
            if not cand_cat and isinstance(cand, SoftwareCatalog):
                cand_cat = cand
            if not cand_cat:
                continue

            c_path = getattr(cand, "install_path", None)
            c_name = getattr(cand, "raw_display_name", getattr(cand_cat, "name", ""))
            c_exe, c_adir, _ = extract_path_components(c_path, c_name)
            score = 0.0

            # Сравнение исполняемых файлов
            if exe_name and c_exe and exe_name == c_exe:
                if is_generic:
                    if app_dir and c_adir and (app_dir == c_adir or app_dir in c_adir or c_adir in app_dir):
                        score += 0.70
                    else:
                        continue
                else:
                    score += 0.50

            # Сравнение папок приложения
            if app_dir and c_adir:
                if app_dir == c_adir:
                    score += 0.35
                elif app_dir in c_adir or c_adir in app_dir:
                    score += 0.30
                else:
                    dir_sim = compute_string_similarity(app_dir, c_adir)
                    if dir_sim >= 0.60:
                        score += 0.25 * dir_sim

            # Сравнение издателя
            pub_given = (publisher or "").strip().lower()
            pub_cand = (getattr(cand, "raw_publisher", None) or getattr(cand_cat, "vendor", None) or "").strip().lower()
            if pub_given and pub_cand:
                if pub_given == pub_cand or pub_given in pub_cand or pub_cand in pub_given:
                    score += 0.20
                else:
                    pub_sim = compute_string_similarity(pub_given, pub_cand)
                    if pub_sim >= 0.50:
                        score += 0.15 * pub_sim

            # Сравнение имени процесса с эталоном
            name_sim = compute_string_similarity(clean_name, cand_cat.name)
            if name_sim >= 0.50:
                score += 0.15 * name_sim

            if score > best_score:
                best_score = score
                best_match_cat = cand_cat

    # 2. Если в InstalledSoftware не найдено, сверяем путь и exe с корпоративным каталогом SoftwareCatalog
    if best_score < 0.70 and catalog_items:
        for cat in catalog_items:
            cat_low = cat.name.lower()
            cat_vendor = (cat.vendor or "").lower()
            score = 0.0

            if app_dir:
                if app_dir in cat_low or cat_low in app_dir:
                    score += 0.50
                elif compute_string_similarity(app_dir, cat.name) >= 0.60:
                    score += 0.40

            if exe_name and not is_generic:
                exe_token = clean_process_name(exe_name).lower()
                if exe_token in cat_low or cat_low in exe_token:
                    score += 0.35
                elif compute_string_similarity(exe_token, cat.name) >= 0.55:
                    score += 0.25

            pub_given = (publisher or "").strip().lower()
            if pub_given and cat_vendor:
                if pub_given in cat_vendor or cat_vendor in pub_given:
                    score += 0.25

            if score > best_score:
                best_score = score
                best_match_cat = cat

    # Порог уверенности для принятия решения по путям и файлам: 0.70
    if best_match_cat and best_score >= 0.70:
        cat_id = best_match_cat.id
        cat_name = best_match_cat.name
        cat_vendor = best_match_cat.vendor or publisher or "Неизвестный вендор"
        cat_category = best_match_cat.category_id or 1
        confidence = round(min(0.96, max(0.88, best_score)), 2)

        # Сохраняем в process_signatures (самообучение)
        # Если передан новый хэш файла, он теперь сохранён и привязан к каталогу!
        await save_learned_signature(
            db=db,
            process_name=raw_process_name,
            normalized_name=cat_name,
            binary_hash=binary_hash,
            catalog_software_id=cat_id,
            ru_registry_id=getattr(best_match_cat, "ru_registry_id", None),
            vendor=cat_vendor,
            confidence=confidence,
            match_source="path_heuristic",
        )

        version_info = f", актуальная версия: '{reported_version}'" if reported_version else ""
        return {
            "matched_catalog_software_id": str(cat_id),
            "matched_name": cat_name,
            "vendor": cat_vendor,
            "category_id": cat_category,
            "matched_version": reported_version,
            "confidence": confidence,
            "match_source": "path_heuristic",
            "reasoning": (
                f"Эвристическое соответствие по пути установки ('{install_path or 'N/A'}') "
                f"и исполняемому файлу '{exe_name}' с эталонным ПО '{cat_name}' (оценка сходства: {int(best_score * 100)}%{version_info})."
            ),
        }

    return None


# ==========================================
# Шаг 3: Поиск по Единому реестру ПО РФ в БД
# ==========================================
async def match_by_ru_registry(
    db: AsyncSession,
    cleaned_name: str,
    raw_process_name: str,
    catalog_items: List[SoftwareCatalog],
    binary_hash: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    name_low = cleaned_name.lower()
    if len(name_low) < 2:
        return None

    # Поиск в таблице ru_software_registry
    stmt = (
        select(RuSoftwareRegistry)
        .where(
            or_(
                func.lower(RuSoftwareRegistry.name) == name_low,
                func.lower(RuSoftwareRegistry.name).like(f"%{name_low}%"),
                func.lower(RuSoftwareRegistry.alternative_names).like(f"%{name_low}%"),
                RuSoftwareRegistry.alternative_names.ilike(f"%{raw_process_name}%"),
            )
        )
        .limit(10)
    )
    result = await db.execute(stmt)
    registry_items = list(result.scalars().all())
    if not registry_items:
        return None

    best_reg = registry_items[0]
    best_score = 0.0
    for reg in registry_items:
        s = compute_string_similarity(cleaned_name, getattr(reg, "name", ""))
        if s > best_score:
            best_score = s
            best_reg = reg

    if best_score < 0.38:
        return None

    cat_item = _find_catalog_item_by_name(catalog_items, getattr(best_reg, "name", ""))

    cat_id = str(cat_item.id) if cat_item else None
    cat_name = cat_item.name if cat_item else getattr(best_reg, "name", cleaned_name)
    vendor = cat_item.vendor if cat_item else (getattr(best_reg, "vendor_name", None) or "Отечественный разработчик")
    category_id = cat_item.category_id if cat_item else 1
    reg_num = getattr(best_reg, "reg_number", "РФ")
    sw_class = getattr(best_reg, "software_class", "ПО РФ")

    # Сохраняем результат в БД (самообучение)
    await save_learned_signature(
        db=db,
        process_name=raw_process_name,
        normalized_name=cat_name,
        binary_hash=binary_hash,
        catalog_software_id=cat_item.id if cat_item else None,
        ru_registry_id=getattr(best_reg, "id", None),
        vendor=vendor,
        confidence=0.96 if cat_item else 0.93,
        match_source="ru_registry",
    )

    return {
        "matched_catalog_software_id": cat_id,
        "matched_name": cat_name,
        "vendor": vendor,
        "category_id": category_id,
        "confidence": 0.96 if cat_item else 0.93,
        "match_source": "ru_registry",
        "reasoning": f"Идентифицировано в Едином реестре отечественного ПО (№ {reg_num}: '{cat_name}', класс: {sw_class}).",
    }


# ==========================================
# Шаг 3: Поиск через векторные эмбеддинги в БД (OpenAI Embeddings + pgvector)
# ==========================================
async def match_by_vector_embedding(
    db: AsyncSession,
    cleaned_name: str,
    raw_process_name: str,
    catalog_items: List[SoftwareCatalog],
    binary_hash: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    # 1. Генерируем вектор эмбеддинга для входящего процесса
    query_vec = await generate_embedding(cleaned_name)
    if not query_vec:
        return None

    best_match_item = None
    best_sim = 0.0
    match_type = ""

    # 2. Поиск среди process_signatures с сохранёнными векторами
    sig_res = await db.execute(
        select(ProcessSignature).where(ProcessSignature.embedding.is_not(None)).limit(200)
    )
    signatures = sig_res.scalars().all()
    for s in signatures:
        if s.embedding:
            sim = compute_cosine_similarity(query_vec, s.embedding)
            if sim > best_sim:
                best_sim = sim
                best_match_item = s
                match_type = "signature"

    # 3. Поиск среди ru_software_registry с эмбеддингами
    reg_res = await db.execute(
        select(RuSoftwareRegistry).where(RuSoftwareRegistry.embedding.is_not(None)).limit(200)
    )
    reg_items = reg_res.scalars().all()
    for r in reg_items:
        if r.embedding:
            sim = compute_cosine_similarity(query_vec, r.embedding)
            if sim > best_sim:
                best_sim = sim
                best_match_item = r
                match_type = "registry"

    # 4. Порог сходства по косинусному расстоянию (порог >= 0.82)
    if best_match_item and best_sim >= 0.82:
        if match_type == "signature":
            sig = best_match_item
            sig.times_matched += 1
            await db.commit()
            cat_sw = sig.catalog_software
            return {
                "matched_catalog_software_id": str(sig.catalog_software_id) if sig.catalog_software_id else None,
                "matched_name": cat_sw.name if cat_sw else sig.normalized_name,
                "vendor": cat_sw.vendor if cat_sw else sig.vendor,
                "category_id": cat_sw.category_id if cat_sw else 1,
                "confidence": round(best_sim, 2),
                "match_source": "embedding",
                "reasoning": f"Семантическое совпадение векторного эмбеддинга ({int(best_sim * 100)}%) с базой знаний ('{sig.normalized_name}').",
            }
        elif match_type == "registry":
            reg = best_match_item
            cat_item = _find_catalog_item_by_name(catalog_items, reg.name)
            cat_id = str(cat_item.id) if cat_item else None
            cat_name = cat_item.name if cat_item else reg.name

            # Сохраняем в process_signatures
            await save_learned_signature(
                db=db,
                process_name=raw_process_name,
                normalized_name=cat_name,
                binary_hash=binary_hash,
                catalog_software_id=cat_item.id if cat_item else None,
                ru_registry_id=reg.id,
                vendor=cat_item.vendor if cat_item else reg.vendor_name,
                confidence=round(best_sim, 2),
                match_source="embedding",
                embedding=query_vec,
            )
            return {
                "matched_catalog_software_id": cat_id,
                "matched_name": cat_name,
                "vendor": cat_item.vendor if cat_item else (reg.vendor_name or "Отечественный разработчик"),
                "category_id": cat_item.category_id if cat_item else 1,
                "confidence": round(best_sim, 2),
                "match_source": "embedding",
                "reasoning": f"Векторный поиск по Единому реестру ПО РФ выявил соответствие с '{reg.name}' (косинусное сходство: {int(best_sim * 100)}%).",
            }

    return None


# ==========================================
# Шаг 4: Поиск через Wikimedia Semantic Search API
# ==========================================
def _query_wikimedia_sync(query: str) -> Optional[Dict[str, str]]:
    params = urllib.parse.urlencode({
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srnamespace": "0",
        "srlimit": "2",
        "format": "json",
    })
    for lang in ["ru", "en"]:
        url = f"https://{lang}.wikipedia.org/w/api.php?{params}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "SAM-SoftwareAssetManagement/1.0 (compliance@sam-enterprise.ru)"}
        )
        try:
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                search_res = data.get("query", {}).get("search", [])
                if search_res:
                    first = search_res[0]
                    title = first.get("title", "")
                    snippet = re.sub(r"<[^>]+>", "", first.get("snippet", ""))
                    return {"title": title, "snippet": snippet}
        except Exception:
            continue
    return None


async def match_by_wikimedia(
    db: AsyncSession,
    cleaned_name: str,
    raw_process_name: str,
    catalog_items: List[SoftwareCatalog],
    binary_hash: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    try:
        wiki_data = await asyncio.to_thread(_query_wikimedia_sync, cleaned_name)
    except Exception:
        wiki_data = None

    if not wiki_data or not wiki_data.get("title"):
        return None

    title = wiki_data["title"]
    snippet = wiki_data.get("snippet", "")

    # Проверяем, есть ли заголовок статьи среди каталога
    cat_item = _find_catalog_item_by_name(catalog_items, title)
    if not cat_item:
        cat_item = _find_catalog_item_by_name(catalog_items, f"{title} {snippet}")

    # Генерируем эмбеддинг для Википедии
    wiki_vec = await generate_embedding(f"{title} {snippet}")

    # Сохраняем в БД для самообучения
    await save_learned_signature(
        db=db,
        process_name=raw_process_name,
        normalized_name=cat_item.name if cat_item else title,
        binary_hash=binary_hash,
        catalog_software_id=cat_item.id if cat_item else None,
        ru_registry_id=None,
        vendor=cat_item.vendor if cat_item else "По данным Wikimedia",
        confidence=0.90 if cat_item else 0.85,
        match_source="wikimedia",
        embedding=wiki_vec,
    )

    if cat_item:
        return {
            "matched_catalog_software_id": str(cat_item.id),
            "matched_name": cat_item.name,
            "vendor": cat_item.vendor,
            "category_id": cat_item.category_id,
            "confidence": 0.90,
            "match_source": "wikimedia",
            "reasoning": f"Продукт сопоставлен через Wikimedia Semantic Search ('{title}') с каталогом компании '{cat_item.name}'.",
        }
    else:
        return {
            "matched_catalog_software_id": None,
            "matched_name": title,
            "vendor": "По данным Wikimedia",
            "category_id": None,
            "confidence": 0.85,
            "match_source": "wikimedia",
            "reasoning": f"Продукт идентифицирован в энциклопедии Wikimedia как '{title}', однако отсутствует в белом списке разрешённого ПО компании (Shadow IT).",
        }


# ==========================================
# Шаг 5: Использование нейросети (OpenAI LLM)
# ==========================================
async def match_by_openai(
    db: AsyncSession,
    raw_process_name: str,
    publisher: Optional[str],
    catalog_items: List[SoftwareCatalog],
    binary_hash: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    if not settings.OPENAI_API_KEY:
        return None

    try:
        from openai import AsyncOpenAI
    except ImportError:
        return None

    client_kwargs: Dict[str, Any] = {"api_key": settings.OPENAI_API_KEY}
    if settings.OPENAI_BASE_URL:
        client_kwargs["base_url"] = settings.OPENAI_BASE_URL

    client = AsyncOpenAI(**client_kwargs)

    catalog_names = [c.name for c in catalog_items]
    prompt = (
        f"You are a Software Asset Management (SAM) matching assistant.\n"
        f"Task: Identify the canonical software name, vendor, and matching catalog software for this process/binary.\n"
        f"Process name: '{raw_process_name}'\n"
        f"Publisher: '{publisher or 'Unknown'}'\n"
        f"Available Corporate Catalog: {json.dumps(catalog_names, ensure_ascii=False)}\n\n"
        f"Respond ONLY with a valid JSON object in this format:\n"
        f"{{\n"
        f'  "official_name": "Official Product Name",\n'
        f'  "vendor": "Publisher Name",\n'
        f'  "matched_catalog_name": "Exact item from catalog or null",\n'
        f'  "confidence": 0.95,\n'
        f'  "reasoning": "Brief explanation in Russian"\n'
        f"}}"
    )

    try:
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=settings.OPENAI_MODEL or "gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a professional IT asset normalizer. Output JSON only."},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
            ),
            timeout=5.0
        )
        content = response.choices[0].message.content
        if not content:
            return None

        parsed = json.loads(content)
        matched_cat_name = parsed.get("matched_catalog_name")

        cat_item = None
        if matched_cat_name and matched_cat_name != "null":
            cat_item = _find_catalog_item_by_name(catalog_items, matched_cat_name)

        if not cat_item and parsed.get("official_name"):
            cat_item = _find_catalog_item_by_name(catalog_items, parsed["official_name"])

        conf = float(parsed.get("confidence", 0.90))
        official_name = parsed.get("official_name", raw_process_name)
        vendor_name = cat_item.vendor if cat_item else parsed.get("vendor", publisher)

        # Вычисляем эмбеддинг для самообучения
        llm_vec = await generate_embedding(f"{raw_process_name} {official_name} {vendor_name or ''}")

        # Сохраняем в БД process_signatures для мгновенного нахождения в следующий раз!
        await save_learned_signature(
            db=db,
            process_name=raw_process_name,
            normalized_name=cat_item.name if cat_item else official_name,
            binary_hash=binary_hash,
            catalog_software_id=cat_item.id if cat_item else None,
            ru_registry_id=None,
            vendor=vendor_name,
            confidence=conf,
            match_source="openai",
            embedding=llm_vec,
        )

        return {
            "matched_catalog_software_id": str(cat_item.id) if cat_item else None,
            "matched_name": cat_item.name if cat_item else official_name,
            "vendor": vendor_name,
            "category_id": cat_item.category_id if cat_item else None,
            "confidence": conf,
            "match_source": "openai",
            "reasoning": parsed.get("reasoning") or f"Нейросетевая нормализация OpenAI сопоставила '{raw_process_name}' с '{official_name}'.",
        }
    except Exception as e:
        print(f"Notice: OpenAI smart matching failed: {e}")
        return None


# ==========================================
# Поиск по базе данных сохранённых сигнатур (Learned DB Cache)
# ==========================================
async def match_by_db_signatures(
    db: AsyncSession,
    raw_process_name: str,
    cleaned_name: str,
) -> Optional[Dict[str, Any]]:
    raw_low = raw_process_name.lower()
    clean_low = cleaned_name.lower()

    stmt = (
        select(ProcessSignature)
        .where(
            or_(
                func.lower(ProcessSignature.process_name) == raw_low,
                func.lower(ProcessSignature.normalized_name) == clean_low,
                ProcessSignature.normalized_name.ilike(f"%{clean_low}%"),
            )
        )
        .limit(1)
    )
    res = await db.execute(stmt)
    sig = res.scalar_one_or_none()
    if sig:
        sig.times_matched += 1
        await db.commit()
        cat_sw = sig.catalog_software
        return {
            "matched_catalog_software_id": str(sig.catalog_software_id) if sig.catalog_software_id else None,
            "matched_name": cat_sw.name if cat_sw else sig.normalized_name,
            "vendor": cat_sw.vendor if cat_sw else sig.vendor,
            "category_id": cat_sw.category_id if cat_sw else 1,
            "confidence": sig.confidence,
            "match_source": sig.match_source,
            "reasoning": f"Процесс найден в самообучающейся базе сигнатур БД SAM ('{sig.normalized_name}'). Использовано ранее обученное правило ({sig.match_source}).",
        }
    return None


# ==========================================
# Локальный нечёткий поиск по БД каталога (фолбэк)
# ==========================================
def match_by_catalog_fallback(
    cleaned_name: str,
    raw_process_name: str,
    publisher: Optional[str],
    catalog_items: List[SoftwareCatalog],
) -> Dict[str, Any]:
    best_item: Optional[SoftwareCatalog] = None
    best_score: float = 0.0

    for item in catalog_items:
        score = compute_string_similarity(cleaned_name, item.name)
        if publisher and item.vendor:
            pub_score = compute_string_similarity(publisher, item.vendor)
            score = (score * 0.7) + (pub_score * 0.3)

        if score > best_score:
            best_score = score
            best_item = item

    if best_item and best_score >= 0.40:
        confidence = round(min(0.98, max(0.60, best_score * 1.1)), 2)
        return {
            "raw_process_name": raw_process_name,
            "matched_catalog_software_id": str(best_item.id),
            "matched_name": best_item.name,
            "vendor": best_item.vendor,
            "category_id": best_item.category_id,
            "confidence": confidence,
            "match_source": "fuzzy_catalog",
            "reasoning": f"Семантическое сопоставление нормализованного имени '{cleaned_name}' с каталогом разрешённого ПО компании (уверенность: {int(confidence * 100)}%).",
        }

    return {
        "raw_process_name": raw_process_name,
        "matched_catalog_software_id": None,
        "matched_name": cleaned_name.title(),
        "vendor": publisher or "Неизвестный вендор",
        "category_id": None,
        "confidence": 0.20,
        "match_source": "unmatched",
        "reasoning": "ПО не найдено в эталонном белом списке компании (Shadow IT). Рекомендуется верификация администратором.",
    }


# ==========================================
# ГЛАВНЫЙ КОНВЕЙЕР SMART MATCHING:
# 1. Хэш файла в БД (SHA-256)
# 2. Эвристический поиск по БД: Путь установки + Имя .exe + Издатель (с сохранением новой версии)
# 3. База сохранённых сигнатур БД (ранее обученные правила)
# 4. Единый реестр Российского ПО в БД
# 5. Векторный поиск по эмбеддингам в БД (OpenAI text-embedding-3-small + pgvector)
# 6. Wikimedia Semantic Search API (+ сохранение в БД)
# 7. Нейросеть OpenAI LLM (+ сохранение в БД)
# 8. Нечёткий поиск по каталогу разрешённого ПО (фолбэк)
# ==========================================
async def match_raw_process_to_catalog(
    db: AsyncSession,
    raw_process_name: str,
    binary_hash: Optional[str] = None,
    publisher: Optional[str] = None,
    install_path: Optional[str] = None,
    reported_version: Optional[str] = None,
) -> Dict[str, Any]:
    cleaned = clean_process_name(raw_process_name)

    # Загружаем текущий каталог ПО из БД
    cat_result = await db.execute(select(SoftwareCatalog))
    catalog_items = list(cat_result.scalars().all())

    def _enrich_result(res: Dict[str, Any]) -> Dict[str, Any]:
        res["raw_process_name"] = raw_process_name
        if reported_version and not res.get("matched_version"):
            res["matched_version"] = reported_version
        if install_path and not res.get("install_path"):
            res["install_path"] = install_path
        return res

    # Шаг 1: Поиск по хэшу файла в БД
    hash_match = await match_by_hash(db, binary_hash, catalog_items)
    if hash_match:
        return _enrich_result(hash_match)

    # Шаг 2: Эвристический поиск по БД (Путь установки + .exe + Издатель)
    # Позволяет моментально сопоставить софт при минорных обновлениях билдов, сохраняя новую версию
    path_match = await match_by_path_and_executable(
        db=db,
        raw_process_name=raw_process_name,
        install_path=install_path,
        reported_version=reported_version,
        publisher=publisher,
        catalog_items=catalog_items,
        binary_hash=binary_hash,
    )
    if path_match:
        return _enrich_result(path_match)

    # Шаг 3: Поиск в таблице ранее обученных сигнатур БД
    db_sig_match = await match_by_db_signatures(db, raw_process_name, cleaned)
    if db_sig_match:
        return _enrich_result(db_sig_match)

    # Шаг 4: Поиск в Едином реестре Российского ПО в БД
    ru_reg_match = await match_by_ru_registry(db, cleaned, raw_process_name, catalog_items, binary_hash)
    if ru_reg_match:
        return _enrich_result(ru_reg_match)

    # Шаг 5: Векторный поиск по эмбеддингам в БД (OpenAI Embeddings)
    vec_match = await match_by_vector_embedding(db, cleaned, raw_process_name, catalog_items, binary_hash)
    if vec_match:
        return _enrich_result(vec_match)

    # Шаг 6: Поиск через Wikimedia Semantic Search API (+ сохранение в БД)
    wiki_match = await match_by_wikimedia(db, cleaned, raw_process_name, catalog_items, binary_hash)
    if wiki_match and wiki_match.get("matched_catalog_software_id"):
        return _enrich_result(wiki_match)

    # Шаг 7: Нейросеть (OpenAI LLM) (+ сохранение в БД)
    ai_match = await match_by_openai(db, raw_process_name, publisher, catalog_items, binary_hash)
    if ai_match and ai_match.get("matched_catalog_software_id"):
        return _enrich_result(ai_match)

    if wiki_match:
        return _enrich_result(wiki_match)

    if ai_match:
        return _enrich_result(ai_match)

    # Шаг 8: Фолбэк нечёткого поиска по каталогу разрешённого ПО
    fallback = match_by_catalog_fallback(cleaned, raw_process_name, publisher, catalog_items)
    if fallback.get("matched_catalog_software_id"):
        # Сохраняем успешный фолбэк в БД для ускорения
        await save_learned_signature(
            db=db,
            process_name=raw_process_name,
            normalized_name=fallback["matched_name"],
            binary_hash=binary_hash,
            catalog_software_id=uuid.UUID(fallback["matched_catalog_software_id"]),
            ru_registry_id=None,
            vendor=fallback.get("vendor"),
            confidence=fallback["confidence"],
            match_source="fuzzy_catalog",
        )
    return _enrich_result(fallback)
