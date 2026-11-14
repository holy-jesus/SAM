from typing import Dict, Any, List
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def process_ai_chat_query(db: AsyncSession, query: str) -> Dict[str, Any]:
    q = query.lower()

    # 1. License Deficit & Financial Overuse Risk
    if any(k in q for k in ["нелицензион", "дефицит", "штраф", "перерасход", "нехватк", "баланс"]):
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
                "answer": "В системе SAM дефицита лицензий не обнаружено. Все фактические инсталляции покрыты закупленными лицензиями (баланс положительный).",
                "sql_executed": sql.strip(),
                "data": [],
            }

        total_penalty = sum(float(r["penalty_rub"]) for r in data)
        items_desc = []
        for r in data:
            items_desc.append(
                f"- **{r['software_name']}**: закуплено {r['purchased']} шт., установлено {r['installed']} шт. "
                f"(дефицит: **{r['deficit']} шт.**). Расчётный штрафной риск: **{float(r['penalty_rub']):,.2f} руб.**"
            )

        answer = (
            f"Анализ фактических инсталляций выявил превышение закупленных лицензий по {len(data)} продуктам:\n\n"
            + "\n".join(items_desc)
            + f"\n\nОбщий суммарный финансовый штрафной риск составляет **{total_penalty:,.2f} руб.** Рекомендуется докупить лицензии или провести инвентаризацию рабочих мест."
        )
        return {
            "answer": answer,
            "sql_executed": sql.strip(),
            "data": data,
        }

    # 2. Zombie Software & Dismissed Employees
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
            f"Обнаружено **{len(data)} фактов простоя лицензий**:\n"
            f"- У уволенных сотрудников: {dismissed_count} ПК с активным ПО.\n"
            f"- Не запускалось более 60 дней: {inactive_count} инсталляций.\n\n"
            f"Рекомендуется высвободить данные лицензии обратно в корпоративный пул свободных лицензий."
        )
        return {
            "answer": answer,
            "sql_executed": sql.strip(),
            "data": data,
        }

    # 3. Prohibited Software & Shadow IT
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

    # 4. General System Overview / Computers / Employees count
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
