import urllib.parse
from html.parser import HTMLParser
from typing import List, Dict, Any, Optional
import requests
from sqlalchemy import select, or_, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from sam.models.substitution import ImportSubstitution
from sam.models.registry import RuSoftwareRegistry
from sam.models.catalog import SoftwareCatalog

# Заголовки, точно воспроизводящие браузерный запрос из HAR-файла
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
    Выполняет реальный сетевой HTTP-запрос к сервису импортозамещения reestr.digital.gov.ru,
    воспроизводя браузерную сессию (куки, заголовки, Referer) по структуре из HAR-дампа.
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
    except Exception as e:
        print(f"Notice: Live request to reestr.digital.gov.ru failed: {e}")
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
    catalog_software_id: Optional[Any] = None,
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


async def search_import_substitutions(
    db: AsyncSession,
    query: str,
    force_fetch: bool = False,
) -> List[ImportSubstitution]:
    """
    Поиск аналогов импортозамещения:
    1. Ищет в локальной БД.
    2. Если нет (или force_fetch=True), делает сетевой запрос к reestr.digital.gov.ru
       с браузерными заголовками и куками по образцу HAR.
    3. Парсит возвращенную HTML-страницу и сохраняет аналоги в БД.
    4. Возвращает список объектов ImportSubstitution.
    """
    clean_q = query.strip()
    if not clean_q:
        return []

    if not force_fetch:
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

    # Выполняем HTTP-запрос к reestr.digital.gov.ru
    html_content = fetch_live_substitution(clean_q)
    if html_content:
        items = parse_substitution_html(html_content, foreign_query=clean_q)
        if items:
            await save_substitution_items_to_db(db, items)

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
