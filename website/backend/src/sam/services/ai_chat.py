import asyncio
import json
import re
from typing import Dict, Any, List, Optional
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sam.config import settings

# Описание схемы базы данных SAM для генерации Text-to-SQL через OpenAI API
SAM_DATABASE_SCHEMA_PROMPT = """
Ты — интеллектуальный ассистент ИТ-директора в корпоративной системе Software Asset Management (SAM) на базе PostgreSQL.
Твоя задача — преобразовывать естественно-языковые вопросы пользователя в безопасные SQL-запросы к базе данных и формировать детальные аналитические отчеты на русском языке.

СХЕМА ТАБЛИЦ БАЗЫ ДАННЫХ SAM:
1. `computers` (Рабочие станции и серверы компании):
   - id (UUID, PK)
   - hostname (VARCHAR, имя хоста)
   - ip_address (VARCHAR, IP-адрес)
   - mac_address (VARCHAR)
   - os_name (VARCHAR, e.g. 'Windows 11 Pro', 'Ubuntu 22.04', 'Astra Linux')
   - os_version (VARCHAR)
   - cpu_info (VARCHAR), ram_total_gb (FLOAT), disk_free_gb (FLOAT)
   - is_online (BOOLEAN, статус сети)
   - last_seen_at (TIMESTAMP)
   - employee_id (UUID, FK -> employees.id, ответственный сотрудник)
   - enrollment_status (VARCHAR: 'approved', 'pending', 'blocked')

2. `employees` (Сотрудники компании):
   - id (UUID, PK)
   - full_name (VARCHAR, ФИО)
   - email (VARCHAR)
   - department (VARCHAR, e.g. 'Бухгалтерия', 'IT', 'Маркетинг', 'Отдел продаж', 'Юристы')
   - position (VARCHAR, должность)
   - status (VARCHAR: 'active' - работает, 'on_leave' - в отпуске, 'dismissed' - уволен)

3. `software_catalog` (Корпоративный белый список разрешенного ПО):
   - id (UUID, PK)
   - name (VARCHAR, официальное наименование ПО, e.g. 'Microsoft Office 2021', 'Astra Linux', '1C:Предприятие', 'Adobe Photoshop')
   - vendor (VARCHAR, вендор)
   - license_type (VARCHAR: 'Commercial', 'Open Source', 'Freeware', 'Trial')
   - max_installations (INT, лимит установок, 0 = без ограничений)
   - has_substitution (BOOLEAN, флаг наличия отечественного аналога в РФ)
   - category_id (INT, FK -> software_categories.id)
   - classifier_id (INT, FK -> software_classifiers.id)

4. `installed_software` (Фактические установки ПО на компьютерах):
   - id (UUID, PK)
   - computer_id (UUID, FK -> computers.id)
   - catalog_software_id (UUID, FK -> software_catalog.id, NULL если софт не опознан)
   - category_id (INT, FK -> software_categories.id)
   - raw_display_name (VARCHAR, имя исполняемого файла или процесса)
   - raw_version (VARCHAR, версия)
   - is_deleted (BOOLEAN, true если софт удален, false если реально установлен)
   - last_launched_at (TIMESTAMP, дата последнего запуска)

5. `licenses` (Закупленные лицензии компании):
   - id (UUID, PK)
   - software_id (UUID, FK -> software_catalog.id)
   - license_key (VARCHAR)
   - license_type (VARCHAR: 'Commercial', 'Subscription', 'OEM', 'Volume', 'Perpetual')
   - total_purchased (INT, закупленное количество лицензий)
   - used_count (INT, количество используемых)
   - unit_cost (NUMERIC, стоимость одной лицензии в рублях)
   - currency (VARCHAR, 'RUB')
   - valid_to (TIMESTAMP, дата окончания подписки или техподдержки)

6. `software_categories` (Категории политики комплаенса):
   - id (INT, PK)
   - name (VARCHAR: 'Актуальный', 'Устаревший', 'Запрещенный к использованию')
   - is_problematic (BOOLEAN, признак проблемы)
   - risk_level (VARCHAR: 'none', 'low', 'medium', 'critical')

7. `compliance_alerts` (Активные инциденты комплаенса и риски):
   - id (UUID, PK)
   - alert_type (VARCHAR: 'license_overuse', 'zombie_software', 'prohibited_software', 'unapproved_software', 'license_expiring_soon')
   - severity (VARCHAR: 'critical', 'high', 'medium', 'low')
   - title (VARCHAR)
   - description (TEXT)
   - financial_risk_amount (NUMERIC, финансовый риск в рублях)
   - status (VARCHAR: 'active', 'resolved', 'ignored')

8. `vulnerabilities` (Уязвимости БДУ ФСТЭК / CVE):
   - id (UUID, PK)
   - identifier (VARCHAR, e.g. 'BDU:2024-00123')
   - name (VARCHAR)
   - cvss3_score (FLOAT, 0.0 - 10.0)
   - severity (VARCHAR: 'critical', 'high', 'medium', 'low')

9. `ru_software_registry` (Единый реестр отечественного ПО):
   - id (INT, PK)
   - reg_number (VARCHAR), name (TEXT), software_class (TEXT), vendor_name (TEXT)

10. `software_classifiers` (Классификатор классов ПО Минцифры):
    - id (INT, PK), code (VARCHAR, e.g. '04.03'), section_name (TEXT), class_name (TEXT)

ПРАВИЛА БЕЗОПАСНОСТИ И ГЕНЕРАЦИИ SQL:
1. Разрешены ТОЛЬКО операции чтения: `SELECT` (или `WITH ... SELECT`).
2. Категорически ЗАПРЕЩЕНЫ любые команды модификации: INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE, INTO.
3. При запросах к `installed_software` ВСЕГДА используй условие `installed_software.is_deleted = false`.
4. Для дефицита лицензий сравнивай количество установок `COUNT(i.id)` с суммой закупленных лицензий `COALESCE(SUM(l.total_purchased), 0)`.
5. Простаивающее ПО («зомби-софт»): ПО у уволенных сотрудников (`e.status = 'dismissed'`) или где `i.last_launched_at < NOW() - INTERVAL '60 days'`.
6. Запрещённый софт (Shadow IT): категория `cat.is_problematic = true` или `cat.risk_level = 'critical'`.
7. Обязательно добавляй `LIMIT 50` во все запросы без групповых агрегатов.
8. Если вопрос носит общий консультационный характер (методология SAM, закон об импортозамещении 188-ФЗ, правила лицензирования) и не требует обращения к БД, укажи `"needs_sql": false`.

ФОРМАТ ОТВЕТА (ТОЛЬКО JSON):
{
  "needs_sql": true,
  "sql": "SELECT ...",
  "explanation": "Краткое пояснение запроса"
}
"""


def is_safe_select_query(sql: str) -> bool:
    """
    Проверяет, что SQL-запрос является исключительно безопасным SELECT-запросом на чтение.
    Блокирует любые деструктивные или изменяющие операции.
    """
    clean = re.sub(r"--.*?$", "", sql, flags=re.MULTILINE).strip()
    clean = re.sub(r"/\*.*?\*/", "", clean, flags=re.DOTALL).strip()
    if not clean:
        return False

    first_word = clean.split()[0].upper()
    if first_word not in ("SELECT", "WITH"):
        return False

    forbidden = [
        "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE",
        "CREATE", "REPLACE", "GRANT", "REVOKE", "EXEC", "EXECUTE",
        "PG_SLEEP", "INTO"
    ]
    pattern = r"\b(" + "|".join(forbidden) + r")\b"
    if re.search(pattern, clean, re.IGNORECASE):
        return False

    return True


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
        print(f"Notice: failed to initialize AsyncOpenAI client: {e}")
        return None


async def _run_ai_chat_with_openai(
    client: Any,
    db: AsyncSession,
    query: str
) -> Optional[Dict[str, Any]]:
    """
    Основной пайплайн реального OpenAI API:
    1. Генерация Text-to-SQL через OpenAI Chat Completion.
    2. Безопасное исполнение сгенерированного SQL в PostgreSQL.
    3. Синтез развернутого ответа на русском языке через OpenAI.
    """
    # Шаг 1. Обращение к OpenAI для извлечения намерения и Text-to-SQL
    sql_intent_resp = await asyncio.wait_for(
        client.chat.completions.create(
            model=settings.OPENAI_MODEL or "gpt-4o-mini",
            messages=[
                {"role": "system", "content": SAM_DATABASE_SCHEMA_PROMPT},
                {"role": "user", "content": f"Вопрос пользователя: {query}"},
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
        ),
        timeout=12.0
    )

    content = sql_intent_resp.choices[0].message.content or "{}"
    parsed_intent = json.loads(content)

    needs_sql = parsed_intent.get("needs_sql", False)
    sql = parsed_intent.get("sql")

    # Если вопрос консультационный (не требует БД)
    if not needs_sql or not sql:
        consultation_resp = await asyncio.wait_for(
            client.chat.completions.create(
                model=settings.OPENAI_MODEL or "gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Ты — главный эксперт по Software Asset Management (SAM), лицензированию ПО и импортозамещению (188-ФЗ). "
                            "Дай развернутый, структурированный и практичный ответ на русском языке в формате Markdown. "
                            "Выделяй важные термины жирным шрифтом и приводи рекомендации."
                        ),
                    },
                    {"role": "user", "content": query},
                ],
                temperature=0.3,
            ),
            timeout=12.0
        )
        answer = consultation_resp.choices[0].message.content or ""
        return {
            "answer": answer.strip(),
            "sql_executed": None,
            "data": [],
        }

    # Шаг 2. Проверка безопасности сгенерированного SQL
    if not is_safe_select_query(sql):
        print(f"Warning: OpenAI generated non-safe SQL: {sql}")
        return None

    # Шаг 3. Исполнение SQL в базе данных SAM
    try:
        db_res = await db.execute(text(sql))
        rows = db_res.mappings().all()
        data = [dict(r) for r in rows]
    except Exception as sql_err:
        print(f"Notice: OpenAI generated SQL failed execution: {sql_err}")
        return None

    # Шаг 4. Синтез аналитического ответа ИТ-директору на основе полученных данных
    synthesis_prompt = (
        f"Пользователь спросил: «{query}»\n\n"
        f"Исполненный SQL-запрос:\n```sql\n{sql}\n```\n\n"
        f"Данные из базы данных SAM (найдено строк: {len(data)}):\n"
        f"{json.dumps(data[:35], ensure_ascii=False, default=str)}\n\n"
        "Сформируй развернутый, профессиональный и структурированный ответ для ИТ-директора компании на русском языке (Markdown).\n"
        "1. Четко ответь на вопрос пользователя, опираясь на факты из данных выше.\n"
        "2. Выдели жирным шрифтом ключевые числа, суммы рисков и названия продуктов/хостов.\n"
        "3. Если обнаружен дефицит лицензий, простаивающий софт или запрещенное ПО — дай конкретные рекомендации по устранению (Remediation Plan)."
    )

    synthesis_resp = await asyncio.wait_for(
        client.chat.completions.create(
            model=settings.OPENAI_MODEL or "gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Ты — цифровой советник и аналитик ИТ-директора по управлению программными активами (SAM). "
                        "Твои ответы точны, подкреплены цифрами из предоставленных данных и оформлены красивым Markdown."
                    ),
                },
                {"role": "user", "content": synthesis_prompt},
            ],
            temperature=0.2,
        ),
        timeout=15.0
    )

    answer = synthesis_resp.choices[0].message.content or ""
    return {
        "answer": answer.strip(),
        "sql_executed": sql.strip(),
        "data": data,
    }


async def _fallback_deterministic_analysis(db: AsyncSession, query: str) -> Dict[str, Any]:
    """
    Резервный детерминированный аналитический движок SAM.
    Срабатывает при недоступности сети, отсутствии ключа OpenAI или ошибках API,
    гарантируя 100% надежность и отсутствие 500 ошибок в UI.
    """
    q = query.lower()

    # 1. Дефицит лицензий и финансовые риски штрафов
    if any(k in q for k in ["нелицензион", "дефицит", "штраф", "перерасход", "нехватк", "баланс", "лицензи"]):
        sql = """
        SELECT s.name AS software_name,
               COALESCE(SUM(l.total_purchased), 0) AS purchased,
               COUNT(i.id) AS installed,
               (COUNT(i.id) - COALESCE(SUM(l.total_purchased), 0)) AS deficit,
               COALESCE(MAX(l.unit_cost), 0) AS unit_cost,
               (COUNT(i.id) - COALESCE(SUM(l.total_purchased), 0)) * COALESCE(MAX(l.unit_cost), 0) AS penalty_rub
        FROM software_catalog s
        LEFT JOIN licenses l ON l.software_id = s.id
        JOIN installed_software i ON i.catalog_software_id = s.id AND i.is_deleted = false
        GROUP BY s.id, s.name
        HAVING COUNT(i.id) > COALESCE(SUM(l.total_purchased), 0);
        """
        result = await db.execute(text(sql))
        rows = result.mappings().all()
        data = [dict(r) for r in rows]

        if not data:
            return {
                "answer": "В корпоративной сети SAM дефицита лицензий не обнаружено. Все фактические инсталляции полностью покрыты закупленными лицензиями (баланс положительный).",
                "sql_executed": sql.strip(),
                "data": [],
            }

        total_penalty = sum(float(r["penalty_rub"]) for r in data)
        items_desc = [
            f"- **{r['software_name']}**: закуплено {r['purchased']} шт., установлено {r['installed']} шт. "
            f"(дефицит: **{r['deficit']} шт.**). Расчётный штрафной риск: **{float(r['penalty_rub']):,.2f} руб.**"
            for r in data
        ]

        answer = (
            f"Анализ фактических инсталляций выявил дефицит лицензий по {len(data)} продуктам:\n\n"
            + "\n".join(items_desc)
            + f"\n\nОбщий суммарный финансовый штрафной риск составляет **{total_penalty:,.2f} руб.** Рекомендуется докупить лицензии или провести аудит рабочих мест."
        )
        return {
            "answer": answer,
            "sql_executed": sql.strip(),
            "data": data,
        }

    # 2. Зомби-софт и уволенные сотрудники
    if any(k in q for k in ["зомби", "простаива", "уволен", "не использу", "не запуска"]):
        sql = """
        SELECT c.hostname,
               COALESCE(e.full_name, 'Не привязан') AS employee,
               COALESCE(e.status, 'none') AS employee_status,
               COALESCE(s.name, i.raw_display_name) AS software_name,
               i.last_launched_at
        FROM installed_software i
        JOIN computers c ON i.computer_id = c.id
        LEFT JOIN employees e ON c.employee_id = e.id
        LEFT JOIN software_catalog s ON i.catalog_software_id = s.id
        WHERE (e.status = 'dismissed' OR i.last_launched_at < NOW() - INTERVAL '60 days')
          AND i.is_deleted = false
        LIMIT 25;
        """
        result = await db.execute(text(sql))
        rows = result.mappings().all()
        data = [dict(r) for r in rows]

        if not data:
            return {
                "answer": "Простаивающего ПО («зомби-софт») и закреплённых ПК за уволенными сотрудниками не выявлено. Все лицензии активно используются.",
                "sql_executed": sql.strip(),
                "data": [],
            }

        dismissed_count = sum(1 for r in data if r["employee_status"] == "dismissed")
        inactive_count = len(data) - dismissed_count

        answer = (
            f"Обнаружено **{len(data)} фактов неэффективного использования лицензий**:\n"
            f"- У уволенных сотрудников: **{dismissed_count} ПК** с активным ПО.\n"
            f"- Не запускалось более 60 дней: **{inactive_count} инсталляций**.\n\n"
            f"Рекомендуется высвободить данные лицензии обратно в корпоративный пул свободных лицензий компании."
        )
        return {
            "answer": answer,
            "sql_executed": sql.strip(),
            "data": data,
        }

    # 3. Запрещенное ПО и Shadow IT
    if any(k in q for k in ["запрещ", "торрент", "shadow", "опасн", "неавториз", "риск"]):
        sql = """
        SELECT c.hostname,
               c.ip_address,
               COALESCE(e.full_name, 'Не назначен') AS employee,
               i.raw_display_name AS process_name,
               cat.name AS category_name,
               cat.risk_level
        FROM installed_software i
        JOIN computers c ON i.computer_id = c.id
        LEFT JOIN employees e ON c.employee_id = e.id
        JOIN software_categories cat ON i.category_id = cat.id
        WHERE (cat.is_problematic = true OR cat.risk_level = 'critical')
          AND i.is_deleted = false;
        """
        result = await db.execute(text(sql))
        rows = result.mappings().all()
        data = [dict(r) for r in rows]

        if not data:
            return {
                "answer": "В корпоративной сети не зафиксировано активных установок ПО из категории «Запрещенный к использованию» или критических угроз.",
                "sql_executed": sql.strip(),
                "data": [],
            }

        answer = (
            f"ВНИМАНИЕ! Найдено **{len(data)} инсталляций запрещённого ПО** в сети предприятия:\n\n"
            + "\n".join(
                [
                    f"- **{r['process_name']}** на ПК `{r['hostname']}` (IP: {r['ip_address'] or 'N/A'}, пользователь: {r['employee']})"
                    for r in data[:10]
                ]
            )
            + "\n\nРекомендуется немедленно изолировать данные хосты и произвести деинсталляцию силами отдела ИБ."
        )
        return {
            "answer": answer,
            "sql_executed": sql.strip(),
            "data": data,
        }

    # 4. Общая сводка системы SAM
    sql = """
    SELECT 
        (SELECT COUNT(*) FROM computers) AS total_computers,
        (SELECT COUNT(*) FROM computers WHERE is_online = true) AS online_computers,
        (SELECT COUNT(*) FROM employees) AS total_employees,
        (SELECT COUNT(*) FROM installed_software WHERE is_deleted = false) AS total_installations,
        (SELECT COUNT(*) FROM compliance_alerts WHERE status = 'active') AS active_alerts,
        COALESCE((SELECT SUM(financial_risk_amount) FROM compliance_alerts WHERE status = 'active'), 0) AS total_risk;
    """
    result = await db.execute(text(sql))
    row = dict(result.mappings().one())

    answer = (
        f"Текущая сводка системы Software Asset Management (SAM):\n\n"
        f"- **Компьютеров на учёте**: {row['total_computers']} (из них {row['online_computers']} онлайн)\n"
        f"- **Сотрудников**: {row['total_employees']}\n"
        f"- **Всего зафиксировано инсталляций ПО**: {row['total_installations']}\n"
        f"- **Активных проблем комплаенса**: {row['active_alerts']}\n"
        f"- **Суммарный финансовый риск**: {float(row['total_risk']):,.2f} руб.\n\n"
        f"Вы можете задать конкретный вопрос: *«У кого стоит нелицензионный софт?»*, *«Сколько лицензий простаивает?»* или *«Покажи ПК с запрещённым софтом»*."
    )
    return {
        "answer": answer,
        "sql_executed": sql.strip(),
        "data": [row],
    }


async def process_ai_chat_query(db: AsyncSession, query: str) -> Dict[str, Any]:
    """ 
    Главная точка входа для обработки запроса в чат-ассистент:
    1. Если настроен OpenAI API — отправляет запрос в реальную модель через AsyncOpenAI:
       генерирует безопасный SQL (Text-to-SQL), выполняет его в базе данных и синтезирует аналитику.
    2. При ошибках внешнего API или сетевых ограничениях — автоматически переключается
       на резервный детерминированный движок, гарантируя бесперебойную работу.
    """
    client = get_openai_client()
    if client is not None:
        try:
            ai_result = await _run_ai_chat_with_openai(client=client, db=db, query=query)
            if ai_result is not None:
                return ai_result
        except Exception as e:
            print(f"Notice: OpenAI chat processing encountered an error: {e}. Falling back to deterministic engine.")

    # Резервный расчет
    return await _fallback_deterministic_analysis(db, query)

