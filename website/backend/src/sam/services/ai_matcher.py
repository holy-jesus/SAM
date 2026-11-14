import re
import difflib
from typing import Optional, Tuple, Dict, Any, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sam.models.catalog import SoftwareCatalog
from sam.models.category import SoftwareCategory


# Alias mapping for typical Windows / Linux executable binaries to canonical product names
PROCESS_ALIAS_MAP: Dict[str, str] = {
    "studio_visual": "Microsoft Visual Studio 2022 Professional",
    "visual_studio": "Microsoft Visual Studio 2022 Professional",
    "devenv": "Microsoft Visual Studio 2022 Professional",
    "msvc": "Microsoft Visual Studio 2022 Professional",
    "chrome": "Google Chrome",
    "google_chrome": "Google Chrome",
    "firefox": "Mozilla Firefox",
    "winword": "Microsoft Office 2021 Professional Plus",
    "excel": "Microsoft Office 2021 Professional Plus",
    "powerpnt": "Microsoft Office 2021 Professional Plus",
    "outlook": "Microsoft Office 2021 Professional Plus",
    "ms_office": "Microsoft Office 2021 Professional Plus",
    "office": "Microsoft Office 2021 Professional Plus",
    "code": "Visual Studio Code",
    "vscode": "Visual Studio Code",
    "pycharm": "JetBrains PyCharm Professional",
    "pycharm64": "JetBrains PyCharm Professional",
    "idea": "JetBrains IntelliJ IDEA Ultimate",
    "idea64": "JetBrains IntelliJ IDEA Ultimate",
    "7z": "7-Zip",
    "7zfm": "7-Zip",
    "7zg": "7-Zip",
    "utorrent": "BitTorrent / uTorrent Client",
    "bittorrent": "BitTorrent / uTorrent Client",
    "torrent": "BitTorrent / uTorrent Client",
    "telegram": "Telegram Desktop",
    "notepad++": "Notepad++",
    "notepadplusplus": "Notepad++",
    "git": "Git for Windows",
    "docker": "Docker Desktop",
    "1cv8": "1С:Предприятие 8",
    "1cv8c": "1С:Предприятие 8",
    "yandex": "Яндекс Браузер",
    "amibig": "Амибиг",
}


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

    # Token set intersection
    tokens1 = set(re.findall(r"\w+", s1_low))
    tokens2 = set(re.findall(r"\w+", s2_low))
    if not tokens1 or not tokens2:
        return 0.0

    jaccard = len(tokens1 & tokens2) / len(tokens1 | tokens2)
    seq = difflib.SequenceMatcher(None, s1_low, s2_low).ratio()
    return max(jaccard, seq)


async def match_raw_process_to_catalog(
    db: AsyncSession,
    raw_process_name: str,
    publisher: Optional[str] = None
) -> Dict[str, Any]:
    cleaned = clean_process_name(raw_process_name)
    raw_lower = raw_process_name.lower()
    cleaned_lower = cleaned.lower()

    # 1. Fetch active software catalog
    result = await db.execute(select(SoftwareCatalog))
    catalog_items = result.scalars().all()

    # Check alias dictionary first
    for alias_key, target_name in PROCESS_ALIAS_MAP.items():
        if alias_key in raw_lower or alias_key in cleaned_lower:
            # Find item in catalog matching target_name
            for item in catalog_items:
                if target_name.lower() in item.name.lower() or item.name.lower() in target_name.lower():
                    return {
                        "raw_process_name": raw_process_name,
                        "matched_catalog_software_id": str(item.id),
                        "matched_name": item.name,
                        "vendor": item.vendor,
                        "category_id": item.category_id,
                        "confidence": 0.95,
                        "reasoning": f"Системный алиас процесса '{raw_process_name}' сопоставлен с эталонным ПО '{item.name}' ({item.vendor or 'Корпоративный софт'}).",
                    }

    # 2. Fuzzy match against catalog items
    best_item: Optional[SoftwareCatalog] = None
    best_score: float = 0.0

    for item in catalog_items:
        score = compute_string_similarity(cleaned, item.name)
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
            "reasoning": f"Семантическое сопоставление нормализованного имени '{cleaned}' с каталогом разрешённого ПО компании (уверенность: {int(confidence * 100)}%).",
        }

    # 3. Unmatched / Shadow IT
    return {
        "raw_process_name": raw_process_name,
        "matched_catalog_software_id": None,
        "matched_name": cleaned.title(),
        "vendor": publisher or "Неизвестный вендор",
        "category_id": None,
        "confidence": 0.20,
        "reasoning": "ПО не найдено в эталонном белом списке компании (Shadow IT). Рекомендуется проверка администратора.",
    }
