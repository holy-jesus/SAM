import asyncio
import json
import re
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from sam.config import settings

# Системный промпт для глубокого юридического и комплаенс-анализа EULA через OpenAI
EULA_ANALYSIS_SYSTEM_PROMPT = """
Ты — ведущий юрист и эксперт по комплаенсу лицензий на программное обеспечение (Software Asset Management, EULA & License Compliance).
Твоя задача — детально проанализировать предоставленный текст лицензионного соглашения (EULA, Terms of Service, License Agreement) и выявить ключевые риски для организации.

КРИТЕРИИ АНАЛИЗА:
1. Коммерческое использование (commercial_use_allowed):
   - Разрешено ли использование юридическим лицом в штатной предпринимательской/корпоративной деятельности компании.
   - Если лицензия предназначена исключительно для личного, домашнего, образовательного или некоммерческого использования (Personal / Non-commercial / Educational Use Only), то commercial_use_allowed = false (риск ответственности по ст. 146 УК РФ и ст. 1301 ГК РФ).
2. Скрытые автопродления и платежи (has_auto_renewal):
   - Условия автоматического продления подписки (auto-renew / recurring payments / регулярные списания), если отказ не оформлен заранее.
3. Пробный период (trial_period_days):
   - Ограничение по сроку действия ознакомительной версии в днях (например 14, 30, 60 дней) или null, если лицензия постоянная либо триал не указан.
4. Ключевые ограничения и риски ИБ / аудита (key_restrictions):
   - Запрет обратной разработки (reverse engineering), декомпиляции;
   - Право правообладателя на проведение инспекций/аудита ИТ-инфраструктуры клиента;
   - Сбор персональных данных, телеметрии и диагностической информации вендором;
   - Территориальные или санкционные ограничения.
5. Уровень общего риска (risk_level):
   - "critical" — прямо запрещено коммерческое использование или нарушаются законы РФ;
   - "high" — агрессивный аудит вендора с финансовыми штрафами или критические ограничения;
   - "medium" — скрытые автопродления, короткий триал (<15 дней), передача телеметрии;
   - "low" — стандартные прозрачные корпоративные условия без скрытых угроз.
6. Экспертное резюме на русском языке (summary_ru):
   - Структурированное, четкое заключение для ИТ-директора с описанием рисков и рекомендациями (Markdown).

ФОРМАТ ВЫВОДА (СТРОГО ВАЛИДНЫЙ JSON):
{
  "commercial_use_allowed": true,
  "risk_level": "critical" | "high" | "medium" | "low",
  "has_auto_renewal": false,
  "trial_period_days": 30,
  "key_restrictions": [
    "Ограничение 1...",
    "Ограничение 2..."
  ],
  "summary_ru": "Развернутый анализ на русском языке с выводами и рекомендациями..."
}
"""


def get_openai_client() -> Optional[Any]:
    """
    Инициализирует и возвращает клиент AsyncOpenAI с настройками из settings.
    """
    if not settings.OPENAI_API_KEY:
        return None

    try:
        from openai import AsyncOpenAI
        client_kwargs: Dict[str, Any] = {"api_key": settings.OPENAI_API_KEY}
        if settings.OPENAI_BASE_URL:
            client_kwargs["base_url"] = settings.OPENAI_BASE_URL
        return AsyncOpenAI(**client_kwargs)
    except Exception as e:
        print(f"Notice: failed to initialize AsyncOpenAI client in ai_eula: {e}")
        return None


async def _run_eula_analysis_with_openai(client: Any, eula_text: str) -> Optional[Dict[str, Any]]:
    """
    Выполняет анализ текста EULA через OpenAI API (модель из settings.OPENAI_MODEL или gpt-4o-mini).
    """
    clean_text = eula_text.strip()
    if len(clean_text) > 25000:
        clean_text = clean_text[:25000] + "\n\n[...Текст соглашения сокращен до 25 000 символов...]"

    resp = await asyncio.wait_for(
        client.chat.completions.create(
            model=settings.OPENAI_MODEL or "gpt-4o-mini",
            messages=[
                {"role": "system", "content": EULA_ANALYSIS_SYSTEM_PROMPT},
                {"role": "user", "content": f"Текст лицензионного соглашения (EULA) для анализа:\n\n{clean_text}"},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        ),
        timeout=20.0
    )

    content = resp.choices[0].message.content or "{}"
    data = json.loads(content)

    commercial_allowed = bool(data.get("commercial_use_allowed", True))
    raw_risk = str(data.get("risk_level", "")).strip().lower()
    if raw_risk in ("critical", "high", "medium", "low"):
        risk_level = raw_risk
    else:
        risk_level = "critical" if not commercial_allowed else "low"

    has_auto_renewal = bool(data.get("has_auto_renewal", False))

    trial_days = data.get("trial_period_days")
    if trial_days is not None:
        try:
            trial_days = int(trial_days)
        except (ValueError, TypeError):
            trial_days = None

    raw_restrictions = data.get("key_restrictions", [])
    if isinstance(raw_restrictions, list):
        key_restrictions = [str(r).strip() for r in raw_restrictions if r]
    elif raw_restrictions:
        key_restrictions = [str(raw_restrictions).strip()]
    else:
        key_restrictions = []

    summary_ru = str(data.get("summary_ru", "")).strip()
    if not summary_ru:
        summary_ru = (
            "Анализ лицензионного соглашения выполнен с помощью модели OpenAI. "
            f"Коммерческое использование: {'разрешено' if commercial_allowed else 'запрещено'}."
        )

    return {
        "commercial_use_allowed": commercial_allowed,
        "risk_level": risk_level,
        "has_auto_renewal": has_auto_renewal,
        "trial_period_days": trial_days,
        "key_restrictions": key_restrictions,
        "summary_ru": summary_ru,
        "analyzed_at": datetime.now(timezone.utc),
    }


def _fallback_deterministic_eula_analysis(eula_text: str) -> Dict[str, Any]:
    """
    Резервный детерминированный движок анализа EULA на основе регулярных выражений и эвристик.
    Срабатывает при отсутствии ключа OpenAI или ошибках подключения к API, гарантируя 100% стабильность.
    """
    text_lower = eula_text.lower()

    # 1. Commercial use detection
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


async def analyze_eula_text(eula_text: str) -> Dict[str, Any]:
    """
    Главная точка входа для анализа лицензионного соглашения (EULA):
    1. Если настроен OpenAI API — отправляет текст соглашения в модель OpenAI (AsyncOpenAI)
       для выделения ключевых рисков, проверки коммерческого использования, скрытых условий и триалов.
    2. При ошибках внешнего API, сетевых ограничениях или отсутствии ключа — автоматически
       переключается на резервный детерминированный движок (rule-based/regex), гарантируя бесперебойную работу.
    """
    client = get_openai_client()
    if client is not None:
        try:
            res = await _run_eula_analysis_with_openai(client=client, eula_text=eula_text)
            if res is not None:
                return res
        except Exception as e:
            print(f"Notice: OpenAI EULA analysis encountered an error: {e}. Falling back to deterministic engine.")

    return _fallback_deterministic_eula_analysis(eula_text)
