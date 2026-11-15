import re
import time
import uuid
import asyncio
import urllib.parse
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser
from typing import List, Dict, Any, Optional, Tuple
import requests
from sqlalchemy import select, or_, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from sam.models.substitution import ImportSubstitution, SubstitutionCache
from sam.models.registry import RuSoftwareRegistry
from sam.models.catalog import SoftwareCatalog

# ==========================================
# Заголовки, точно воспроизводящие браузерный запрос из HAR-файла
# ==========================================
BROWSER_HEADERS = {
    "Host": "reestr.digital.gov.ru",
    "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:154.0) Gecko/20100101 Firefox/154.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
    "Referer": "https://reestr.digital.gov.ru/import-substitution/",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
}

AJAX_HEADERS = {
    "Host": "reestr.digital.gov.ru",
    "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:154.0) Gecko/20100101 Firefox/154.0",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
    "Bx-ajax": "true",
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/x-www-form-urlencoded",
    "Referer": "https://reestr.digital.gov.ru/import-substitution/",
    "Origin": "https://reestr.digital.gov.ru",
}

# Срок актуальности кэша в БД (дней)
CACHE_TTL_DAYS = 14
DOMESTIC_CACHE_TTL_DAYS = 30
ERROR_CACHE_TTL_DAYS = 1


# ==========================================
# Rate Limiter для защиты от DDoS и блокировок
# ==========================================
class SubstitutionRateLimiter:
    """
    Асинхронный ограничитель частоты сетевых запросов (Rate Limiter) с защитой от DDoS
    и поддержкой экспоненциального отката при ошибках сети или HTTP 429 (Too Many Requests).
    Гарантирует паузу не менее min_interval (по умолчанию 1.5 сек) между вызовами.
    """
    def __init__(self, min_interval: float = 1.5):
        self.min_interval = min_interval
        self._lock = asyncio.Lock()
        self._last_request_time: float = 0.0
        self._backoff_delay: float = 0.0

    async def acquire(self):
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request_time
            required_wait = self.min_interval + self._backoff_delay
            if elapsed < required_wait:
                sleep_time = required_wait - elapsed
                await asyncio.sleep(sleep_time)
            self._last_request_time = time.monotonic()
            if self._backoff_delay > 0:
                self._backoff_delay = max(0.0, self._backoff_delay - 0.5)

    def trigger_backoff(self, delay: float = 5.0):
        """Увеличивает задержку при 429 или временных сетевых ошибках."""
        self._backoff_delay = min(30.0, self._backoff_delay + delay)

    def reset(self):
        self._last_request_time = 0.0
        self._backoff_delay = 0.0


# Глобальный экземпляр Rate Limiter
rate_limiter = SubstitutionRateLimiter(min_interval=1.5)


# ==========================================
# Распознавание официального названия ПО
# ==========================================
UNOFFICIAL_EXECUTABLES = {
    "setup.exe", "install.exe", "installer.exe", "uninstall.exe", "unins000.exe",
    "uninst.exe", "update.exe", "updater.exe", "patch.exe", "helper.exe",
    "service.exe", "agent.exe", "host.exe", "client.exe", "server.exe",
    "start.exe", "run.exe", "app.exe", "main.exe", "cli.exe", "svchost.exe",
    "cmd.exe", "powershell.exe", "conhost.exe", "explorer.exe", "taskmgr.exe",
    "dllhost.exe", "runtimebroker.exe", "backgroundtaskhost.exe", "msiexec.exe",
    "rundll32.exe", "regsvr32.exe", "system", "idle", "registry"
}


def is_official_software_name(name: str) -> bool:
    """
    Проверяет, является ли название софта официальным и распознанным,
    а не сырым именем исполняемого файла (.exe) или служебным процессом.
    """
    if not name or not isinstance(name, str):
        return False
    clean = name.strip()
    if len(clean) < 2:
        return False
    low = clean.lower()
    if low in UNOFFICIAL_EXECUTABLES:
        return False
    # Исключаем сырые ненормализованные имена файлов .exe, .msi, .dll, .sys, .bin, .tmp
    if re.search(r"\.(exe|msi|dll|sys|tmp|bin|bat|cmd|sh|ps1)$", low, flags=re.IGNORECASE):
        return False
    # Исключаем строки, состоящие только из цифр и знаков
    if not re.search(r"[a-zA-Zа-яА-Я]", clean):
        return False
    return True


# ==========================================
# Проверка наличия в Едином реестре ПО РФ
# ==========================================
async def check_is_in_ru_registry(
    db: AsyncSession,
    software_name: str,
    catalog_software_id: Optional[uuid.UUID] = None,
) -> Tuple[bool, Optional[int]]:
    """
    Проверяет, зарегистрировано ли данное ПО в Едином реестре российских программ
    для ЭВМ и БД (Минцифры РФ). Если ПО есть в реестре РФ, оно уже является
    отечественным, и поиск импортозамещения для него не требуется.
    """
    clean_name = software_name.strip()
    name_low = clean_name.lower()

    # 1. Если передан catalog_software_id, проверяем прямую привязку каталога к Реестру
    if catalog_software_id:
        cat_stmt = select(SoftwareCatalog.ru_registry_id).where(SoftwareCatalog.id == catalog_software_id)
        ru_reg_id = (await db.execute(cat_stmt)).scalar_one_or_none()
        if ru_reg_id:
            return True, ru_reg_id

    # 2. Проверяем в ru_software_registry по точному совпадению или границам слов
    if len(name_low) <= 5:
        reg_stmt = select(RuSoftwareRegistry.id).where(
            or_(
                func.lower(RuSoftwareRegistry.name) == name_low,
                func.lower(RuSoftwareRegistry.name).like(f"{name_low} %"),
                func.lower(RuSoftwareRegistry.name).like(f"% {name_low}"),
                func.lower(RuSoftwareRegistry.name).like(f"% {name_low} %"),
                func.lower(RuSoftwareRegistry.alternative_names) == name_low,
            )
        ).limit(1)
    else:
        reg_stmt = select(RuSoftwareRegistry.id).where(
            or_(
                func.lower(RuSoftwareRegistry.name) == name_low,
                func.lower(RuSoftwareRegistry.name).like(f"%{name_low}%"),
                func.lower(RuSoftwareRegistry.alternative_names).like(f"%{name_low}%"),
            )
        ).limit(1)

    reg_id = (await db.execute(reg_stmt)).scalar_one_or_none()
    if reg_id:
        return True, reg_id

    return False, None


# ==========================================
# Кэш в БД с ограничением по времени (TTL)
# ==========================================
async def get_cached_substitution_status(
    db: AsyncSession,
    software_name: str,
) -> Optional[SubstitutionCache]:
    """
    Возвращает актуальную (не просроченную) запись из таблицы substitution_cache.
    Если запись просрочена или отсутствует, возвращает None.
    """
    clean_name = software_name.strip().lower()
    stmt = select(SubstitutionCache).where(
        func.lower(SubstitutionCache.software_name) == clean_name
    )
    cache_entry = (await db.execute(stmt)).scalar_one_or_none()
    if cache_entry:
        now = datetime.now(timezone.utc)
        if cache_entry.expires_at > now:
            return cache_entry
    return None


async def save_substitution_cache_record(
    db: AsyncSession,
    software_name: str,
    has_substitution: bool,
    substitutions_count: int,
    is_domestic: bool,
    status: str,
    catalog_software_id: Optional[uuid.UUID] = None,
    error_message: Optional[str] = None,
    ttl_days: int = CACHE_TTL_DAYS,
) -> SubstitutionCache:
    """
    Сохраняет результат проверки в таблицу substitution_cache с указанием срока действия (TTL).
    Также обновляет поля has_substitution и substitutions_count в software_catalog (если привязан).
    """
    clean_name = software_name.strip()
    name_low = clean_name.lower()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=ttl_days)

    stmt = select(SubstitutionCache).where(
        func.lower(SubstitutionCache.software_name) == name_low
    )
    cache_entry = (await db.execute(stmt)).scalar_one_or_none()

    if cache_entry:
        cache_entry.has_substitution = has_substitution
        cache_entry.substitutions_count = substitutions_count
        cache_entry.is_domestic = is_domestic
        cache_entry.status = status
        cache_entry.last_checked_at = now
        cache_entry.expires_at = expires_at
        cache_entry.error_message = error_message
        if catalog_software_id and not cache_entry.catalog_software_id:
            cache_entry.catalog_software_id = catalog_software_id
    else:
        cache_entry = SubstitutionCache(
            software_name=clean_name,
            has_substitution=has_substitution,
            substitutions_count=substitutions_count,
            is_domestic=is_domestic,
            status=status,
            catalog_software_id=catalog_software_id,
            last_checked_at=now,
            expires_at=expires_at,
            error_message=error_message,
        )
        db.add(cache_entry)

    # Обновляем флаги в software_catalog, если указан catalog_software_id
    if catalog_software_id:
        cat_stmt = select(SoftwareCatalog).where(SoftwareCatalog.id == catalog_software_id)
        cat_item = (await db.execute(cat_stmt)).scalar_one_or_none()
        if cat_item:
            cat_item.has_substitution = has_substitution
            cat_item.substitutions_count = substitutions_count

    await db.commit()
    return cache_entry


# ==========================================
# HTML-парсер страниц сервиса импортозамещения
# ==========================================
class SubstitutionHTMLParser(HTMLParser):
    """
    HTML-парсер страниц сервиса импортозамещения reestr.digital.gov.ru.
    Извлекает карточки отечественных аналогов (.collection-item.a-link).
    """
    def __init__(self, foreign_query: str = ""):
        super().__init__()
        self.foreign_query = foreign_query
        self.results: List[Dict[str, Any]] = []
        self.current_item: Optional[Dict[str, Any]] = None
        self.current_data_name: Optional[str] = None
        self.current_class: Optional[str] = None
        self.current_tab: str = "registry"

    def handle_starttag(self, tag: str, attrs: List[tuple]):
        attr_dict = dict(attrs)

        if "data-tab" in attr_dict:
            self.current_tab = attr_dict["data-tab"]

        classes = attr_dict.get("class", "").split()
        if "collection-item" in classes and "a-link" in classes:
            href = attr_dict.get("data-href", "")
            if href.startswith("/"):
                href = f"https://reestr.digital.gov.ru{href}"
            self.current_item = {
                "foreign_software_name": self.foreign_query,
                "registry_url": href,
                "source": self.current_tab or "registry",
                "russian_reg_number": "",
                "registration_date": "",
                "russian_software_name": "",
                "owner_name": "",
                "class_code": "",
                "class_name": "",
            }
            self.results.append(self.current_item)

        if self.current_item is not None:
            if "data-name" in attr_dict:
                self.current_data_name = attr_dict["data-name"]
            if "class" in attr_dict:
                self.current_class = attr_dict["class"]

    def handle_data(self, data: str):
        text = data.strip()
        if not text or not self.current_item:
            return

        if self.current_data_name == "№ реестровой записи":
            self.current_item["russian_reg_number"] = (self.current_item["russian_reg_number"] + " " + text).strip()
        elif self.current_data_name == "Дата регистрации":
            self.current_item["registration_date"] = (self.current_item["registration_date"] + " " + text).strip()
        elif self.current_data_name == "Наименование ПО":
            self.current_item["russian_software_name"] = (self.current_item["russian_software_name"] + " " + text).strip()
        elif self.current_data_name == "Правообладатель":
            self.current_item["owner_name"] = (self.current_item["owner_name"] + " " + text).strip()
        elif self.current_data_name == "Класс ПО":
            if self.current_class == "class-code":
                self.current_item["class_code"] = (self.current_item["class_code"] + " " + text).strip()
            elif self.current_class == "class-item":
                self.current_item["class_name"] = (self.current_item["class_name"] + " " + text).strip()


def parse_substitution_html(html_content: str, foreign_query: str) -> List[Dict[str, Any]]:
    """Парсит HTML-страничку импортозамещения и возвращает структурированный список аналогов."""
    parser = SubstitutionHTMLParser(foreign_query=foreign_query)
    parser.feed(html_content)

    # Дедупликация распарсенных результатов
    unique_items: List[Dict[str, Any]] = []
    seen = set()
    for it in parser.results:
        key = (
            it.get("foreign_software_name", "").strip().lower(),
            it.get("russian_software_name", "").strip().lower(),
            it.get("russian_reg_number", "").strip(),
        )
        if key not in seen and it.get("russian_software_name"):
            seen.add(key)
            unique_items.append(it)

    return unique_items


def fetch_live_substitution(foreign_software_query: str) -> Optional[str]:
    """
    Синхронный HTTP-запрос к сервису импортозамещения reestr.digital.gov.ru
    с воспроизведением браузерной сессии из HAR-дампа.
    """
    clean_q = foreign_software_query.strip()
    encoded = urllib.parse.quote(clean_q)
    url = f"https://reestr.digital.gov.ru/import-substitution/?query={encoded}"

    session = requests.Session()
    session.verify = False
    session.headers.update(BROWSER_HEADERS)

    try:
        # Прогрев для получения сессионных кук Bitrix
        session.get("https://reestr.digital.gov.ru/import-substitution/", timeout=4, verify=False)
        resp = session.get(url, timeout=8)
        if resp.status_code == 200 and len(resp.text) > 500:
            return resp.text
        elif resp.status_code == 429:
            rate_limiter.trigger_backoff(delay=10.0)
    except Exception as e:
        rate_limiter.trigger_backoff(delay=3.0)
        print(f"Notice: Live request to reestr.digital.gov.ru failed: {e}")
    return None


async def fetch_live_substitution_rate_limited(foreign_software_query: str) -> Optional[str]:
    """
    Асинхронная обёртка с соблюдением Rate Limiter для предотвращения DDoS.
    Выполняет блокирующий requests-вызов в пуле потоков loop.run_in_executor.
    """
    await rate_limiter.acquire()
    loop = asyncio.get_running_loop()
    try:
        return await loop.run_in_executor(None, fetch_live_substitution, foreign_software_query)
    except Exception as e:
        print(f"RateLimiter executor error for '{foreign_software_query}': {e}")
        return None


def fetch_product_suggestions(query: str) -> List[str]:
    """
    Запрашивает подсказки автодополнения иностранного софта через Bitrix AJAX API
    (по образцу Entry 1 из HAR-дампа).
    """
    url = "https://reestr.digital.gov.ru/bitrix/services/main/ajax.php?mode=class&c=ext%3Aimport.substitution.search&action=searchProduct"
    session = requests.Session()
    session.verify = False
    session.headers.update(AJAX_HEADERS)
    try:
        resp = session.post(
            url,
            data={"QUERY": query.strip(), "signedParameters": ""},
            timeout=5,
            verify=False
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("data", {}).get("items", [])
    except Exception:
        pass
    return []


async def save_substitution_items_to_db(
    db: AsyncSession,
    items: List[Dict[str, Any]],
    catalog_software_id: Optional[uuid.UUID] = None,
) -> int:
    """
    Сохраняет найденные аналоги в таблицу import_substitutions,
    автоматически связывая их с ru_software_registry и software_catalog.
    """
    if not items:
        return 0

    added = 0
    for item in items:
        sw_name = item.get("russian_software_name", "").strip()
        foreign_name = item.get("foreign_software_name", "").strip()
        reg_num = item.get("russian_reg_number", "").strip() or None

        if not sw_name or not foreign_name:
            continue

        stmt = select(ImportSubstitution).where(
            and_(
                func.lower(ImportSubstitution.foreign_software_name) == foreign_name.lower(),
                func.lower(ImportSubstitution.russian_software_name) == sw_name.lower(),
            )
        )
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing:
            continue

        # Связываем с ru_software_registry
        ru_reg_id = None
        if reg_num:
            reg_stmt = select(RuSoftwareRegistry.id).where(RuSoftwareRegistry.reg_number == reg_num)
            ru_reg_id = (await db.execute(reg_stmt)).scalar_one_or_none()

        if not ru_reg_id:
            reg_stmt = select(RuSoftwareRegistry.id).where(
                func.lower(RuSoftwareRegistry.name) == sw_name.lower()
            ).limit(1)
            ru_reg_id = (await db.execute(reg_stmt)).scalar_one_or_none()

        # Связываем с software_catalog
        cat_id = catalog_software_id
        if not cat_id:
            cat_stmt = select(SoftwareCatalog.id).where(
                func.lower(SoftwareCatalog.name).like(f"%{foreign_name.lower()}%")
            ).limit(1)
            cat_id = (await db.execute(cat_stmt)).scalar_one_or_none()

        sub_obj = ImportSubstitution(
            foreign_software_name=foreign_name,
            russian_software_name=sw_name,
            russian_reg_number=reg_num,
            source=item.get("source", "registry"),
            owner_name=item.get("owner_name") or None,
            class_code=item.get("class_code") or None,
            class_name=item.get("class_name") or None,
            registration_date=item.get("registration_date") or None,
            registry_url=item.get("registry_url") or None,
            ru_registry_id=ru_reg_id,
            catalog_software_id=cat_id,
        )
        db.add(sub_obj)
        added += 1

    if added > 0:
        await db.commit()

    return added


# ==========================================
# Автоматический конвейер проверки импортозамещения
# ==========================================
async def process_software_substitution(
    db: AsyncSession,
    software_name: str,
    catalog_software_id: Optional[uuid.UUID] = None,
    force_fetch: bool = False,
) -> Dict[str, Any]:
    """
    Полный автоматический конвейер проверки импортозамещения для ПО:
    1. Проверка валидности официального названия.
    2. Проверка наличия в Едином реестре РФ (отечественное ПО не требует импортозамещения).
    3. Проверка кэша в БД substitution_cache (если актуален и не force_fetch).
    4. Запрос к сервису Минцифры через Rate Limiter (защита от DDoS).
    5. Парсинг аналогов, сохранение в import_substitutions.
    6. Запись в substitution_cache с TTL (14 дней).
    7. Обновление флагов в software_catalog.
    """
    if not is_official_software_name(software_name):
        return {
            "status": "skipped_not_official",
            "message": f"'{software_name}' не является официальным распознанным названием ПО.",
            "has_substitution": False,
            "substitutions_count": 0,
            "is_domestic": False,
        }

    clean_name = software_name.strip()

    # 1. Проверяем, зарегистрировано ли в Реестре РФ (отечественное ПО)
    is_domestic, reg_id = await check_is_in_ru_registry(db, clean_name, catalog_software_id)
    if is_domestic:
        await save_substitution_cache_record(
            db=db,
            software_name=clean_name,
            has_substitution=False,
            substitutions_count=0,
            is_domestic=True,
            status="domestic",
            catalog_software_id=catalog_software_id,
            ttl_days=DOMESTIC_CACHE_TTL_DAYS,
        )
        return {
            "status": "domestic",
            "message": f"'{clean_name}' входит в Единый реестр ПО РФ (отечественное ПО).",
            "has_substitution": False,
            "substitutions_count": 0,
            "is_domestic": True,
            "ru_registry_id": reg_id,
        }

    # 2. Проверяем кэш в БД
    if not force_fetch:
        cached = await get_cached_substitution_status(db, clean_name)
        if cached:
            return {
                "status": cached.status,
                "cached": True,
                "has_substitution": cached.has_substitution,
                "substitutions_count": cached.substitutions_count,
                "is_domestic": cached.is_domestic,
                "last_checked_at": cached.last_checked_at,
                "expires_at": cached.expires_at,
            }

    # 3. Выполняем сетевой запрос к reestr.digital.gov.ru через Rate Limiter
    html_content = await fetch_live_substitution_rate_limited(clean_name)
    if html_content:
        items = parse_substitution_html(html_content, foreign_query=clean_name)
        if items:
            await save_substitution_items_to_db(db, items, catalog_software_id=catalog_software_id)

        has_sub = len(items) > 0
        status_str = "checked" if has_sub else "not_found"
        cached = await save_substitution_cache_record(
            db=db,
            software_name=clean_name,
            has_substitution=has_sub,
            substitutions_count=len(items),
            is_domestic=False,
            status=status_str,
            catalog_software_id=catalog_software_id,
            ttl_days=CACHE_TTL_DAYS,
        )
        return {
            "status": status_str,
            "cached": False,
            "has_substitution": has_sub,
            "substitutions_count": len(items),
            "is_domestic": False,
            "last_checked_at": cached.last_checked_at,
            "expires_at": cached.expires_at,
        }
    else:
        # Сеть недоступна или сервис временно не ответил:
        # сохраняем короткий кэш (1 день) чтобы не перегружать сервис
        cached = await save_substitution_cache_record(
            db=db,
            software_name=clean_name,
            has_substitution=False,
            substitutions_count=0,
            is_domestic=False,
            status="error",
            catalog_software_id=catalog_software_id,
            error_message="External service unavailable or rate limited",
            ttl_days=ERROR_CACHE_TTL_DAYS,
        )
        return {
            "status": "error",
            "cached": False,
            "has_substitution": False,
            "substitutions_count": 0,
            "is_domestic": False,
            "message": "Не удалось связаться с сервисом Минцифры reestr.digital.gov.ru",
        }


# ==========================================
# Очередь фоновой обработки с контролем Rate Limit
# ==========================================
_substitution_queue: asyncio.Queue = asyncio.Queue()
_enqueued_names: set = set()
_worker_task: Optional[asyncio.Task] = None


def enqueue_software_substitution_check(
    software_name: str,
    catalog_software_id: Optional[uuid.UUID] = None,
) -> bool:
    """
    Добавляет новое распознанное ПО в фоновую очередь на проверку импортозамещения
    с соблюдением rate-limit. Исключает дублирование повторных запросов.
    """
    if not is_official_software_name(software_name):
        return False
    low = software_name.strip().lower()
    if low in _enqueued_names:
        return False
    _enqueued_names.add(low)
    try:
        _substitution_queue.put_nowait((software_name.strip(), catalog_software_id))
        return True
    except Exception:
        _enqueued_names.discard(low)
        return False


async def _substitution_queue_worker():
    """
    Фоновый рабочий процесс, выбирающий задачи из очереди поочерёдно
    и выполняющий проверку с контролем частоты.
    """
    from sam.db import AsyncSessionLocal
    while True:
        try:
            name, cat_id = await _substitution_queue.get()
            low = name.strip().lower()
            try:
                async with AsyncSessionLocal() as session:
                    await process_software_substitution(
                        db=session,
                        software_name=name,
                        catalog_software_id=cat_id,
                        force_fetch=False,
                    )
            except Exception as e:
                print(f"[!] Ошибка в фоновом воркере импортозамещения для '{name}': {e}")
            finally:
                _substitution_queue.task_done()
                _enqueued_names.discard(low)
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[!] Неожиданное исключение в очереди импортозамещения: {e}")
            await asyncio.sleep(2.0)


def start_substitution_worker():
    """Запускает фоновый воркер обработки очереди."""
    global _worker_task
    if _worker_task is None or _worker_task.done():
        try:
            loop = asyncio.get_running_loop()
            _worker_task = loop.create_task(_substitution_queue_worker())
        except RuntimeError:
            pass


def stop_substitution_worker():
    """Останавливает фоновый воркер обработки очереди."""
    global _worker_task
    if _worker_task and not _worker_task.done():
        _worker_task.cancel()
        _worker_task = None


async def scan_and_queue_unprocessed_catalog(db: AsyncSession) -> int:
    """
    Сканирует весь SoftwareCatalog компании:
    находит всё зарубежное ПО (ru_registry_id IS NULL) с официальными именами,
    для которых ещё нет актуальной записи в substitution_cache,
    и ставит их в очередь на фоновую проверку с rate-limit.
    """
    stmt = (
        select(SoftwareCatalog)
        .where(SoftwareCatalog.ru_registry_id.is_(None))
    )
    res = await db.execute(stmt)
    catalog_items = res.scalars().all()

    enqueued = 0
    now = datetime.now(timezone.utc)
    for cat in catalog_items:
        if not is_official_software_name(cat.name):
            continue

        cache_stmt = select(SubstitutionCache).where(
            func.lower(SubstitutionCache.software_name) == cat.name.strip().lower()
        )
        cache_entry = (await db.execute(cache_stmt)).scalar_one_or_none()
        if cache_entry and cache_entry.expires_at > now:
            # Синхронизируем поля в software_catalog
            if cat.has_substitution != cache_entry.has_substitution:
                cat.has_substitution = cache_entry.has_substitution
                cat.substitutions_count = cache_entry.substitutions_count
            continue

        if enqueue_software_substitution_check(cat.name, catalog_software_id=cat.id):
            enqueued += 1

    await db.commit()
    return enqueued


# ==========================================
# Поиск аналогов импортозамещения (с кэшированием)
# ==========================================
async def search_import_substitutions(
    db: AsyncSession,
    query: str,
    force_fetch: bool = False,
) -> List[ImportSubstitution]:
    """
    Поиск аналогов импортозамещения:
    1. Проверяет, не входит ли продукт в Единый реестр РФ (если отечественное — аналогов не требуется).
    2. Проверяет кэш проверок substitution_cache в БД: если зафиксировано отсутствие аналогов,
       сетевой запрос НЕ делается (экономия ресурсов и защита от DDoS).
    3. Если кэша нет (или force_fetch=True), вызывает process_software_substitution
       через Rate Limiter, парсит страницу и сохраняет результат в БД.
    4. Возвращает список объектов ImportSubstitution.
    """
    clean_q = query.strip()
    if not clean_q:
        return []

    # 1. Проверяем реестр отечественного ПО
    is_domestic, _ = await check_is_in_ru_registry(db, clean_q)
    if is_domestic:
        return []

    # 2. Если не force_fetch, проверяем кэш проверки
    if not force_fetch:
        cached = await get_cached_substitution_status(db, clean_q)
        if cached:
            if not cached.has_substitution:
                # В кэше зафиксировано отсутствие аналогов — внешний сетевой запрос не нужен!
                return []
            stmt = (
                select(ImportSubstitution)
                .where(
                    or_(
                        func.lower(ImportSubstitution.foreign_software_name).like(f"%{clean_q.lower()}%"),
                        func.lower(ImportSubstitution.russian_software_name).like(f"%{clean_q.lower()}%"),
                    )
                )
            )
            existing_items = list((await db.execute(stmt)).scalars().all())
            if existing_items:
                return existing_items

    # 3. Запрос через конвейер
    res = await process_software_substitution(db, clean_q, force_fetch=force_fetch)
    if res.get("is_domestic") or not res.get("has_substitution"):
        return []

    stmt = (
        select(ImportSubstitution)
        .where(
            or_(
                func.lower(ImportSubstitution.foreign_software_name).like(f"%{clean_q.lower()}%"),
                func.lower(ImportSubstitution.russian_software_name).like(f"%{clean_q.lower()}%"),
            )
        )
    )
    return list((await db.execute(stmt)).scalars().all())
