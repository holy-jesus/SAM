import re
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional


def analyze_eula_text(eula_text: str) -> Dict[str, Any]:
    text_lower = eula_text.lower()

    # 1. Commercial use detection
    # Phrases that indicate restriction to non-commercial / personal use only
    non_commercial_patterns = [
        r"non[- ]commercial",
        r"personal use only",
        r"for personal, non[- ]commercial",
        r"not for commercial",
        r"educational use only",
        r"некоммерческ",
        r"исключительно для личн",
        r"только в личных целях",
        r"запрещено использование юридическ",
        r"не предназначено для коммерческ",
        r"только для домашнего",
    ]
    
    # Phrases that explicitly grant commercial use
    commercial_patterns = [
        r"commercial use is permitted",
        r"business and commercial use",
        r"enterprise license",
        r"corporate license",
        r"разрешено коммерческое использование",
        r"корпоративная лицензия",
        r"для юридических лиц",
    ]

    has_non_commercial_restriction = any(re.search(p, text_lower) for p in non_commercial_patterns)
    has_explicit_commercial = any(re.search(p, text_lower) for p in commercial_patterns)

    commercial_use_allowed = has_explicit_commercial or (not has_non_commercial_restriction)

    # 2. Auto-renewal detection
    auto_renew_patterns = [
        r"auto[- ]renew",
        r"automatic renewal",
        r"recurring billing",
        r"recurring payment",
        r"automatic charge",
        r"автоматическ.*продлен",
        r"автоплатеж",
        r"регулярное списание",
        r"периодическая подписка",
    ]
    has_auto_renewal = any(re.search(p, text_lower) for p in auto_renew_patterns)

    # 3. Trial period detection
    trial_period_days = None
    trial_match = re.search(r"(\d+)[- ]day(?:s)?\s+(?:free\s+)?trial", text_lower)
    if not trial_match:
        trial_match = re.search(r"(?:пробный период|триал)[^\d]*(\d+)[- ]?(?:дней|дня|день)", text_lower)
    if trial_match:
        try:
            trial_period_days = int(trial_match.group(1))
        except Exception:
            trial_period_days = 30
    elif "trial" in text_lower or "пробн" in text_lower:
        trial_period_days = 30

    # 4. Synthesize Key Restrictions
    key_restrictions: List[str] = []

    if not commercial_use_allowed:
        key_restrictions.append(
            "Лицензия строго ограничена персональным/некоммерческим использованием (Personal / Non-commercial Use Only). "
            "Использование в коммерческой инфраструктуре компании влечёт риск штрафа по ст. 146 УК РФ и ст. 1301 ГК РФ."
        )
    else:
        key_restrictions.append(
            "Разрешено использование юридическим лицом в рамках штатной коммерческой деятельности."
        )

    if has_auto_renewal:
        key_restrictions.append(
            "Обнаружено условие автоматического продления (Auto-renewal) и регулярного списания платежей при отсутствии отказа за 24-48 часов."
        )

    if trial_period_days:
        key_restrictions.append(
            f"Ограничение пробного периода: {trial_period_days} дней. По истечении срока требуется покупка постоянной коммерческой лицензии или удаление софта."
        )

    if "telemetry" in text_lower or "collect data" in text_lower or "сбор данных" in text_lower or "телеметри" in text_lower:
        key_restrictions.append(
            "В соглашении указан сбор телеметрии и диагностических данных правообладателем. Рекомендуется проверка службой ИБ."
        )

    if "reverse engineer" in text_lower or "декомпиляц" in text_lower:
        key_restrictions.append(
            "Запрет обратной разработки (Reverse Engineering), дизассемблирования и модификации бинарных файлов."
        )

    # 5. Determine Overall Risk Level
    if not commercial_use_allowed:
        risk_level = "critical"
    elif has_auto_renewal or (trial_period_days and trial_period_days < 15):
        risk_level = "medium"
    else:
        risk_level = "low"

    # 6. Generate Russian Summary
    if not commercial_use_allowed:
        summary_ru = (
            "КРИТИЧЕСКИЙ РИСК: Лицензионное соглашение категорически запрещает эксплуатацию софта в коммерческих "
            "целях компании. Установка на рабочие станции сотрудников является прямым нарушением авторских прав "
            "правообладателя и грозит судебными исками с компенсацией до двукратной стоимости софта."
        )
    elif has_auto_renewal:
        summary_ru = (
            "УМЕРЕННЫЙ РИСК: Коммерческое использование допустимо, однако зафиксированы пункты об автоматическом "
            "продлении подписки. Рекомендуется зафиксировать дату окончания в финансовом календаре для избежания "
            "непредвиденных списаний корпоративных средств."
        )
    else:
        summary_ru = (
            "НИЗКИЙ РИСК: Условия соглашения стандартны для корпоративного использования. Существенных правовых "
            "или финансовых рисков для предприятия не выявлено."
        )

    return {
        "commercial_use_allowed": commercial_use_allowed,
        "risk_level": risk_level,
        "has_auto_renewal": has_auto_renewal,
        "trial_period_days": trial_period_days,
        "key_restrictions": key_restrictions,
        "summary_ru": summary_ru,
        "analyzed_at": datetime.now(timezone.utc),
    }
