import asyncio
import json
import re
from contextlib import asynccontextmanager
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
   - serial_number (VARCHAR, серийный номер ПК)
   - hostname (VARCHAR, имя хоста)
   - ip_address (VARCHAR, IP-адрес)
   - mac_address (VARCHAR)
   - os_name (VARCHAR, e.g. 'Windows 11 Pro', 'Ubuntu 22.04', 'Astra Linux')
   - os_version (VARCHAR)
   - cpu_info (VARCHAR), ram_mb (INT, объем оперативной памяти в МБ), disk_info (JSON, данные о дисках)
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
   - user_category (VARCHAR)

3. `software_catalog` (Корпоративный белый список разрешенного ПО):
   - id (UUID, PK)
   - name (VARCHAR, официальное наименование ПО, e.g. 'Microsoft Office 2021', 'Astra Linux', '1C:Предприятие', 'Adobe Photoshop')
   - vendor (VARCHAR, вендор)
   - description (TEXT)
   - license_type (VARCHAR: 'Commercial', 'Free', 'Open Source', 'Subscription')
   - max_installations (INT, лимит установок, 0 = без ограничений)
   - has_substitution (BOOLEAN, флаг наличия отечественного аналога в РФ)
   - substitutions_count (INT, количество найденных отечественных аналогов)
   - category_id (INT, FK -> software_categories.id)
   - classifier_id (INT, FK -> software_classifiers.id)
   - ru_registry_id (INT, FK -> ru_software_registry.id)

4. `installed_software` (Фактические установки ПО на компьютерах):
   - id (UUID, PK)
   - computer_id (UUID, FK -> computers.id)
   - catalog_software_id (UUID, FK -> software_catalog.id, NULL если софт не опознан)
   - category_id (INT, FK -> software_categories.id)
   - raw_display_name (VARCHAR, имя исполняемого файла или процесса)
   - raw_publisher (VARCHAR, издатель)
   - raw_version (VARCHAR, версия)
   - install_path (TEXT)
   - is_deleted (BOOLEAN, true если софт удален, false если реально установлен)
   - last_launched_at (TIMESTAMP, дата последнего запуска)

5. `licenses` (Закупленные лицензии компании):
   - id (UUID, PK)
   - software_id (UUID, FK -> software_catalog.id)
   - license_name (VARCHAR, наименование лицензии)
   - license_type (VARCHAR: 'Commercial', 'Subscription', 'OEM', 'Volume', 'Perpetual', 'Платный')
   - license_model (VARCHAR: 'per_device', 'per_user')
   - total_purchased (INT, закупленное количество лицензий)
   - unit_cost (NUMERIC, стоимость одной лицензии в рублях)
   - currency (VARCHAR, 'RUB')
   - valid_from (DATE, дата начала действия)
   - valid_to (DATE, дата окончания лицензии)
   ВНИМАНИЕ: В таблице `licenses` НЕТ колонки `used_count`! Количество используемых лицензий — это количество активных установок в `installed_software`!

6. `software_categories` (Категории политики комплаенса):
   - id (INT, PK)
   - name (VARCHAR: 'Актуальный', 'Устаревший', 'Запрещенный к использованию')
   - is_problematic (BOOLEAN, признак проблемы)
   - risk_level (VARCHAR: 'none', 'low', 'medium', 'critical')

7. `compliance_alerts` (Активные инциденты комплаенса и риски):
   - id (UUID, PK)
   - alert_type (VARCHAR: 'license_overuse', 'zombie_software', 'prohibited_software', 'shadow_it', 'commercial_risk')
   - severity (VARCHAR: 'critical', 'warning', 'info')
   - computer_id (UUID, FK -> computers.id)
   - software_id (UUID, FK -> software_catalog.id)
   - title (VARCHAR)
   - description (TEXT)
   - financial_risk_amount (NUMERIC, финансовый риск в рублях)
   - status (VARCHAR: 'active', 'acknowledged', 'resolved')

8. `vulnerabilities` (Уязвимости БДУ ФСТЭК / CVE):
   - id (UUID, PK)
   - bdu_id (VARCHAR, e.g. 'BDU:2024-00123')
   - cve_id (TEXT, e.g. 'CVE-2024-1234')
   - name (TEXT)
   - vendor (TEXT)
   - software_name (TEXT)
   - cvss_score (FLOAT, 0.0 - 10.0)
   - severity (VARCHAR: 'Критический', 'Высокий', 'Средний', 'Низкий')

9. `ru_software_registry` (Единый реестр отечественного ПО):
   - id (INT, PK)
   - reg_number (VARCHAR), name (TEXT), software_class (TEXT), vendor_name (TEXT)

10. `software_classifiers` (Классификатор классов ПО Минцифры):
    - id (INT, PK), code (VARCHAR, e.g. '04.03'), section_name (TEXT), class_name (TEXT)

ПРАВИЛА БЕЗОПАСНОСТИ И ГЕНЕРАЦИИ SQL:
1. Разрешены ТОЛЬКО операции чтения: `SELECT` (или `WITH ... SELECT`).
2. Категорически ЗАПРЕЩЕНЫ любые команды модификации: INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE, INTO.
3. При запросах к `installed_software` ВСЕГДА используй условие `installed_software.is_deleted = false`.
4. ВНИМАНИЕ: В таблице `licenses` НЕТ колонки `used_count`! Количество фактически используемых лицензий компании — это количество активных установок ПО: `COUNT(i.id)` из `installed_software i WHERE i.catalog_software_id = sc.id AND i.is_deleted = false`.
   - Для выявления дефицита лицензий сравнивай количество установок `COUNT(i.id)` с суммой закупленных лицензий `COALESCE(SUM(l.total_purchased), 0)`.
   - Простаивающие (свободные) закупленные лицензии: `COALESCE(SUM(l.total_purchased), 0) - COUNT(i.id)` (когда закуплено больше, чем установлено).
5. Простаивающее ПО («зомби-софт»): софт на компьютерах уволенных сотрудников (`e.status = 'dismissed'`) или софт, который не запускался более 60 дней (`i.last_launched_at < NOW() - INTERVAL '60 days' OR i.last_launched_at IS NULL`), где `i.is_deleted = false`.
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


def _extract_json(raw_text: str) -> Dict[str, Any]:
    """Безопасно извлекает JSON-объект из ответа GigaChat (убирая ```json и лишний текст)."""
    match = re.search(r"\{.*\}", raw_text.strip(), re.DOTALL)
    if not match:
        raise ValueError(f"JSON object not found in LLM response: {raw_text[:200]}")
    return json.loads(match.group(0))


@asynccontextmanager
async def _safe_nested_transaction(db: AsyncSession):
    """
    Безопасный контекстный менеджер для выполнения SQL.
    Если передан реальный AsyncSession, использует begin_nested (SAVEPOINT),
    гарантируя изоляцию ошибок и предотвращая переход родительской транзакции в состояние aborted.
    """
    nested = None
    begin_fn = getattr(db, "begin_nested", None)
    if callable(begin_fn) and type(begin_fn).__name__ != "AsyncMock":
        try:
            ctx = begin_fn()
            if hasattr(ctx, "__aenter__") and hasattr(ctx, "__aexit__"):
                nested = ctx
        except Exception:
            nested = None

    if nested is not None:
        async with nested:
            yield
    else:
        yield


async def _run_ai_chat_with_openai(
    client: Any,
    db: AsyncSession,
    query: str
) -> Optional[Dict[str, Any]]:
    """
    Основной пайплайн работы с LLM (адаптировано под GigaChat):
    1. Генерация Text-to-SQL через Chat Completion.
    2. Безопасное исполнение сгенерированного SQL в PostgreSQL.
    3. Синтез развернутого ответа на русском языке.
    """
    # Шаг 1. Извлечение намерения и Text-to-SQL
    sql_intent_resp = await asyncio.wait_for(
        client.chat.completions.create(
            model=settings.OPENAI_MODEL or "GigaChat",
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"{SAM_DATABASE_SCHEMA_PROMPT}\n\n"
                        "ВАЖНО: Верни ответ СТРОГО в виде валидного JSON-объекта без markdown-разметки (без ```json) и без поясняющего текста."
                    ),
                },
                {"role": "user", "content": f"Вопрос пользователя: {query}"},
            ],
            # response_format убран (не поддерживается GigaChat)
            temperature=0.01,
        ),
        timeout=15.0
    )

    content = sql_intent_resp.choices[0].message.content or "{}"
    parsed_intent = _extract_json(content)

    needs_sql = parsed_intent.get("needs_sql", False)
    sql = parsed_intent.get("sql")

    # Если вопрос консультационный (не требует БД)
    if not needs_sql or not sql:
        consultation_resp = await asyncio.wait_for(
            client.chat.completions.create(
                model=settings.OPENAI_MODEL or "GigaChat",
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
            timeout=15.0
        )
        answer = consultation_resp.choices[0].message.content or ""
        return {
            "answer": answer.strip(),
            "sql_executed": None,
            "data": [],
        }

    # Шаг 2. Проверка безопасности сгенерированного SQL
    if not is_safe_select_query(sql):
        print(f"Warning: LLM generated non-safe SQL: {sql}")
        return None

    # Шаг 3. Исполнение SQL в базе данных SAM
    data = None
    executed_sql = sql
    try:
        async with _safe_nested_transaction(db):
            db_res = await db.execute(text(sql))
            rows = db_res.mappings().all()
            data = [dict(r) for r in rows]
    except Exception as sql_err:
        print(f"Notice: LLM generated SQL failed execution: {sql_err}")
        try:
            await db.rollback()
        except Exception:
            pass

        # Однократная попытка авто-исправления запроса моделью с передачей ошибки
        try:
            retry_prompt = (
                f"Сгенерированный ранее SQL-запрос завершился с ошибкой PostgreSQL:\n"
                f"{sql_err}\n\n"
                f"Исходный некорректный SQL:\n{sql}\n\n"
                f"Напоминание: в таблице `licenses` НЕТ колонки `used_count` (используй COUNT(i.id) из `installed_software` с фильтром `is_deleted = false`).\n"
                f"Исправь SQL-запрос для вопроса пользователя: «{query}».\n"
                "Верни ответ СТРОГО в виде JSON: {\"needs_sql\": true, \"sql\": \"...\", \"explanation\": \"...\"}"
            )
            retry_resp = await asyncio.wait_for(
                client.chat.completions.create(
                    model=settings.OPENAI_MODEL or "GigaChat",
                    messages=[
                        {"role": "system", "content": SAM_DATABASE_SCHEMA_PROMPT},
                        {"role": "user", "content": retry_prompt},
                    ],
                    temperature=0.01,
                ),
                timeout=12.0
            )
            retry_content = retry_resp.choices[0].message.content or "{}"
            parsed_retry = _extract_json(retry_content)
            retry_sql = parsed_retry.get("sql")
            if retry_sql and is_safe_select_query(retry_sql):
                async with _safe_nested_transaction(db):
                    db_res = await db.execute(text(retry_sql))
                    rows = db_res.mappings().all()
                    data = [dict(r) for r in rows]
                    executed_sql = retry_sql
        except Exception as retry_err:
            print(f"Notice: retry SQL generation/execution failed: {retry_err}")
            try:
                await db.rollback()
            except Exception:
                pass

    if data is None:
        return None

    # Шаг 4. Синтез аналитического ответа ИТ-директору на основе полученных данных
    synthesis_prompt = (
        f"Пользователь спросил: «{query}»\n\n"
        f"Исполненный SQL-запрос:\n```sql\n{executed_sql}\n```\n\n"
        f"Данные из базы данных SAM (найдено строк: {len(data)}):\n"
        f"{json.dumps(data[:35], ensure_ascii=False, default=str)}\n\n"
        "Сформируй развернутый, профессиональный и структурированный ответ для ИТ-директора компании на русском языке (Markdown).\n"
        "1. Четко ответь на вопрос пользователя, опираясь на факты из данных выше.\n"
        "2. Выдели жирным шрифтом ключевые числа, суммы рисков и названия продуктов/хостов.\n"
        "3. Если обнаружен дефицит лицензий, простаивающий софт или запрещенное ПО — дай конкретные рекомендации по устранению (Remediation Plan)."
    )

    synthesis_resp = await asyncio.wait_for(
        client.chat.completions.create(
            model=settings.OPENAI_MODEL or "GigaChat",
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
        timeout=20.0
    )

    answer = synthesis_resp.choices[0].message.content or ""
    return {
        "answer": answer.strip(),
        "sql_executed": executed_sql.strip(),
        "data": data,
    }

async def _fallback_deterministic_analysis(db: AsyncSession, query: str) -> Dict[str, Any]:
    """
    Резервный детерминированный аналитический движок SAM.
    Срабатывает при недоступности сети, отсутствии ключа OpenAI или ошибках API,
    гарантируя 100% надежность и отсутствие 500 ошибок в UI.
    """
    q = query.lower()

    # Вспомогательная функция безопасного выполнения SQL с гарантированным откатом при сбое
    async def _safe_execute(query_sql: str) -> Optional[List[Dict[str, Any]]]:
        try:
            # begin_nested создает SAVEPOINT, если транзакция активна,
            # и откатывает savepoint при ошибке, сохраняя транзакцию
            async with _safe_nested_transaction(db):
                res = await db.execute(text(query_sql))
                rows = res.mappings().all()
                return [dict(r) for r in rows]
        except Exception as e:
            print(f"Notice: deterministic fallback SQL execution error: {e}")
            try:
                await db.rollback()
            except Exception:
                pass
            return None

    # 1. Зомби-софт, простаивающее ПО и уволенные сотрудники
    if any(k in q for k in ["зомби", "простаива", "простой", "уволен", "не использу", "не запуска", "idle", "zombie"]):
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
        WHERE (e.status = 'dismissed' OR i.last_launched_at < NOW() - INTERVAL '60 days' OR i.last_launched_at IS NULL)
          AND i.is_deleted = false
        ORDER BY (e.status = 'dismissed') DESC, i.last_launched_at ASC NULLS FIRST
        LIMIT 25;
        """
        data = await _safe_execute(sql)
        if data is None:
            return {
                "answer": "В настоящий момент не удалось выполнить аналитический запрос по простаивающему ПО к базе данных.",
                "sql_executed": sql.strip(),
                "data": [],
            }

        if not data:
            return {
                "answer": "Простаивающего ПО («зомби-софт») и закреплённых ПК за уволенными сотрудниками не выявлено. Все лицензии активно используются.",
                "sql_executed": sql.strip(),
                "data": [],
            }

        dismissed_count = sum(1 for r in data if r["employee_status"] == "dismissed")
        inactive_count = len(data) - dismissed_count

        details = [
            f"- **{r['software_name']}** на ПК `{r['hostname']}` (пользователь: {r['employee']}"
            + (", статус: **уволен**" if r["employee_status"] == "dismissed" else f", последний запуск: {str(r['last_launched_at'])[:10] if r['last_launched_at'] else 'не запускался'}")
            + ")"
            for r in data[:10]
        ]

        answer = (
            f"Обнаружено **{len(data)} фактов неэффективного использования лицензий (зомби-софт)**:\n"
            f"- У уволенных сотрудников: **{dismissed_count} ПК** с активными установками ПО.\n"
            f"- Не запускалось более 60 дней: **{inactive_count} инсталляций**.\n\n"
            f"Примеры выявленных установок:\n"
            + "\n".join(details)
            + "\n\nРекомендуется высвободить данные лицензии обратно в корпоративный пул свободных лицензий компании."
        )
        return {
            "answer": answer,
            "sql_executed": sql.strip(),
            "data": data,
        }

    # 2. Запрещенное ПО и Shadow IT
    if any(k in q for k in ["запрещ", "торрент", "shadow", "опасн", "неавториз", "вредонос", "нежелательн"]):
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
          AND i.is_deleted = false
        LIMIT 25;
        """
        data = await _safe_execute(sql)
        if data is None:
            return {
                "answer": "Не удалось выполнить запрос по запрещенному ПО к базе данных.",
                "sql_executed": sql.strip(),
                "data": [],
            }

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

    # 3. Финансовые риски и активные алерты комплаенса
    if any(k in q for k in ["финансов", "риск", "алерт", "инцидент", "ущерб"]):
        sql = """
        SELECT alert_type, severity, title, financial_risk_amount, status
        FROM compliance_alerts
        WHERE status = 'active'
        ORDER BY financial_risk_amount DESC
        LIMIT 20;
        """
        data = await _safe_execute(sql)
        if data is not None and data:
            total_risk = sum(float(r["financial_risk_amount"] or 0) for r in data)
            items = [
                f"- **{r['title']}** (серьёзность: `{r['severity']}`): риск **{float(r['financial_risk_amount'] or 0):,.2f} руб.**"
                for r in data[:8]
            ]
            answer = (
                f"Текущий суммарный финансовый риск компании по активным инцидентам комплаенса составляет **{total_risk:,.2f} руб.**\n\n"
                f"Ключевые инциденты:\n" + "\n".join(items)
            )
            return {
                "answer": answer,
                "sql_executed": sql.strip(),
                "data": data,
            }

    # 4. Дефицит лицензий и финансовые риски штрафов
    if any(k in q for k in ["нелицензион", "дефицит", "штраф", "перерасход", "нехватк", "баланс", "лицензи"]):
        sql = """
        SELECT s.name AS software_name,
               COALESCE(lic.total_purchased, 0) AS purchased,
               inst.installed_count AS installed,
               (inst.installed_count - COALESCE(lic.total_purchased, 0)) AS deficit,
               COALESCE(lic.unit_cost, 0) AS unit_cost,
               (inst.installed_count - COALESCE(lic.total_purchased, 0)) * COALESCE(lic.unit_cost, 0) AS penalty_rub
        FROM software_catalog s
        JOIN (
            SELECT catalog_software_id, COUNT(id) AS installed_count
            FROM installed_software
            WHERE is_deleted = false AND catalog_software_id IS NOT NULL
            GROUP BY catalog_software_id
        ) inst ON inst.catalog_software_id = s.id
        LEFT JOIN (
            SELECT software_id, SUM(total_purchased) AS total_purchased, MAX(unit_cost) AS unit_cost
            FROM licenses
            GROUP BY software_id
        ) lic ON lic.software_id = s.id
        WHERE inst.installed_count > COALESCE(lic.total_purchased, 0)
        ORDER BY penalty_rub DESC
        LIMIT 50;
        """
        data = await _safe_execute(sql)
        if data is None:
            return {
                "answer": "Не удалось выполнить запрос анализа дефицита лицензий к базе данных.",
                "sql_executed": sql.strip(),
                "data": [],
            }

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

    # 5. Общая сводка системы SAM
    sql = """
    SELECT 
        (SELECT COUNT(*) FROM computers) AS total_computers,
        (SELECT COUNT(*) FROM computers WHERE is_online = true) AS online_computers,
        (SELECT COUNT(*) FROM employees) AS total_employees,
        (SELECT COUNT(*) FROM installed_software WHERE is_deleted = false) AS total_installations,
        (SELECT COUNT(*) FROM compliance_alerts WHERE status = 'active') AS active_alerts,
        COALESCE((SELECT SUM(financial_risk_amount) FROM compliance_alerts WHERE status = 'active'), 0) AS total_risk;
    """
    data = await _safe_execute(sql)
    if data is None or not data:
        return {
            "answer": "В настоящий момент сводная информация по системе SAM временно недоступна.",
            "sql_executed": sql.strip(),
            "data": [],
        }

    row = data[0]
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
            try:
                await db.rollback()
            except Exception:
                pass

    # Гарантируем откат перед резервным движком на случай прерванной транзакции
    try:
        await db.rollback()
    except Exception:
        pass

    # Резервный расчет
    return await _fallback_deterministic_analysis(db, query)

