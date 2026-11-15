import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from sam.services.ai_chat import (
    process_ai_chat_query,
    is_safe_select_query,
    get_openai_client,
)


class MockResult:
    def __init__(self, item):
        self.item = item

    def scalar_one_or_none(self):
        return self.item

    def scalar_one(self):
        return self.item

    def scalars(self):
        m = MagicMock()
        m.all.return_value = self.item if isinstance(self.item, list) else [self.item]
        return m

    def mappings(self):
        m = MagicMock()
        m.all.return_value = self.item if isinstance(self.item, list) else [self.item]
        m.one.return_value = self.item[0] if isinstance(self.item, list) and self.item else self.item
        return m

    def all(self):
        return self.item if isinstance(self.item, list) else [self.item]


def test_sql_safety():
    print("--- 1. Testing SQL Safety Validator ---")
    assert is_safe_select_query("SELECT * FROM computers LIMIT 10") is True
    assert is_safe_select_query("WITH stats AS (SELECT count(*) FROM computers) SELECT * FROM stats") is True
    assert is_safe_select_query("select id, name from software_catalog where vendor = 'Microsoft'") is True

    # Dangerous queries must be blocked
    assert is_safe_select_query("DELETE FROM computers") is False
    assert is_safe_select_query("DROP TABLE software_catalog") is False
    assert is_safe_select_query("UPDATE employees SET status = 'dismissed'") is False
    assert is_safe_select_query("INSERT INTO licenses (license_key) VALUES ('x')") is False
    assert is_safe_select_query("SELECT * INTO backup_table FROM computers") is False
    assert is_safe_select_query("ALTER TABLE computers ADD COLUMN hacked text") is False
    assert is_safe_select_query("TRUNCATE TABLE installed_software") is False
    assert is_safe_select_query("") is False
    print("PASS: SQL safety validator successfully blocked dangerous operations and allowed valid SELECT.")


async def test_openai_chat_flow_mocked():
    print("--- 2. Testing Real OpenAI Pipeline with Mocked API Responses ---")
    db = AsyncMock()
    mock_db_rows = [
        {"hostname": "WS-001", "software_name": "Adobe Photoshop", "deficit": 2, "penalty_rub": 120000.0}
    ]
    db.execute.return_value = MockResult(mock_db_rows)

    mock_client = AsyncMock()

    # Step 1: Text-to-SQL completion
    step1_choice = MagicMock()
    step1_choice.message.content = '{"needs_sql": true, "sql": "SELECT hostname FROM computers LIMIT 10", "explanation": "Поиск компьютеров"}'
    step1_resp = MagicMock()
    step1_resp.choices = [step1_choice]

    # Step 2: Synthesis completion
    step2_choice = MagicMock()
    step2_choice.message.content = "Анализ выявил превышение лицензий Adobe Photoshop на рабочей станции WS-001. Суммарный риск: **120,000 руб.**"
    step2_resp = MagicMock()
    step2_resp.choices = [step2_choice]

    mock_client.chat.completions.create.side_effect = [step1_resp, step2_resp]

    with patch("sam.services.ai_chat.get_openai_client", return_value=mock_client):
        res = await process_ai_chat_query(db, "Покажи компьютеры с дефицитом Photoshop")

        assert "120,000 руб." in res["answer"]
        assert res["sql_executed"] == "SELECT hostname FROM computers LIMIT 10"
        assert len(res["data"]) == 1
        assert res["data"][0]["hostname"] == "WS-001"
        assert mock_client.chat.completions.create.call_count == 2

    print("PASS: OpenAI Text-to-SQL + Synthesis pipeline executed cleanly.")


async def test_openai_consultation_flow_mocked():
    print("--- 3. Testing OpenAI Consultation Flow (No SQL needed) ---")
    db = AsyncMock()
    mock_client = AsyncMock()

    # Step 1: LLM says no SQL needed
    step1_choice = MagicMock()
    step1_choice.message.content = '{"needs_sql": false, "sql": null, "explanation": "Консультация по закону"}'
    step1_resp = MagicMock()
    step1_resp.choices = [step1_choice]

    # Step 2: Consultation answer
    step2_choice = MagicMock()
    step2_choice.message.content = "В соответствии с Федеральным законом № 188-ФЗ организации обязаны осуществлять преимущественное использование отечественного ПО из Единого реестра."
    step2_resp = MagicMock()
    step2_resp.choices = [step2_choice]

    mock_client.chat.completions.create.side_effect = [step1_resp, step2_resp]

    with patch("sam.services.ai_chat.get_openai_client", return_value=mock_client):
        res = await process_ai_chat_query(db, "Расскажи про требования закона 188-ФЗ об импортозамещении")

        assert "188-ФЗ" in res["answer"]
        assert res["sql_executed"] is None
        assert res["data"] == []

    print("PASS: Advisory consultation queries answered directly without running SQL.")


async def test_fallback_on_api_error():
    print("--- 4. Testing Fallback to Deterministic Engine on API Exception ---")
    db = AsyncMock()
    mock_overview = [
        {
            "total_computers": 15,
            "online_computers": 12,
            "total_employees": 18,
            "total_installations": 45,
            "active_alerts": 3,
            "total_risk": 250000.0,
        }
    ]
    db.execute.return_value = MockResult(mock_overview)

    mock_client = AsyncMock()
    mock_client.chat.completions.create.side_effect = Exception("OpenAI API Connection Timeout (DNS failed)")

    with patch("sam.services.ai_chat.get_openai_client", return_value=mock_client):
        # Query that falls into general overview fallback
        res = await process_ai_chat_query(db, "Общая сводка по предприятию")

        assert res["answer"] is not None
        assert "Компьютеров на учёте" in res["answer"]
        assert res["sql_executed"] is not None
        assert len(res["data"]) == 1
        assert res["data"][0]["total_computers"] == 15

    print("PASS: Fallback to deterministic analytics succeeded without error.")


async def test_llm_sql_failure_rolls_back_and_falls_back():
    print("--- 5. Testing LLM SQL Error Handling (Transaction Rollback + Safe Fallback) ---")
    db = AsyncMock()

    # First execute fails (simulating Postgres error: column does not exist)
    # Subsequent fallback execute succeeds
    mock_zombie_rows = [
        {
            "hostname": "WS-DISMISSED",
            "employee": "Соколов П.В.",
            "employee_status": "dismissed",
            "software_name": "MS Office 2021",
            "last_launched_at": None,
        }
    ]

    sql_error = Exception("column l.used_count does not exist")
    fallback_result = MockResult(mock_zombie_rows)

    db.execute.side_effect = [sql_error, Exception("retry also failed"), fallback_result]

    mock_client = AsyncMock()
    step1_choice = MagicMock()
    step1_choice.message.content = '{"needs_sql": true, "sql": "SELECT l.used_count FROM licenses l", "explanation": "Ошибочный запрос"}'
    step1_resp = MagicMock()
    step1_resp.choices = [step1_choice]

    mock_client.chat.completions.create.return_value = step1_resp

    with patch("sam.services.ai_chat.get_openai_client", return_value=mock_client):
        res = await process_ai_chat_query(db, "Сколько лицензий простаивает («зомби-софт»)?")

        # Rollback must be called so Postgres transaction is not left in aborted state
        assert db.rollback.call_count >= 1
        assert res["answer"] is not None
        assert "зомби-софт" in res["answer"].lower()
        assert "WS-DISMISSED" in res["answer"]
        assert len(res["data"]) == 1

    print("PASS: Handled SQL failure with transaction rollback and clean fallback without 500 error.")


async def test_deterministic_routing_for_quick_prompts():
    print("--- 6. Testing Deterministic Routing for All Quick Prompts ---")
    mock_client = None  # Force fallback engine

    with patch("sam.services.ai_chat.get_openai_client", return_value=mock_client):
        # 1. Zombie / Idle prompt
        db1 = AsyncMock()
        db1.execute.return_value = MockResult([
            {
                "hostname": "PC-01",
                "employee": "Иванов И.И.",
                "employee_status": "dismissed",
                "software_name": "Adobe Photoshop",
                "last_launched_at": None,
            }
        ])
        res1 = await process_ai_chat_query(db1, "Сколько лицензий простаивает («зомби-софт»)?")
        assert "зомби-софт" in res1["answer"].lower()
        assert "PC-01" in res1["answer"]

        # 2. Deficit / Unlicensed prompt
        db2 = AsyncMock()
        db2.execute.return_value = MockResult([
            {
                "software_name": "MS Office 2021",
                "purchased": 10,
                "installed": 15,
                "deficit": 5,
                "unit_cost": 25000.0,
                "penalty_rub": 125000.0,
            }
        ])
        res2 = await process_ai_chat_query(db2, "У кого стоит нелицензионный софт?")
        assert "дефицит" in res2["answer"].lower()
        assert "MS Office 2021" in res2["answer"]

        # 3. Prohibited software prompt
        db3 = AsyncMock()
        db3.execute.return_value = MockResult([
            {
                "hostname": "WS-TORRENT",
                "ip_address": "192.168.1.100",
                "employee": "Петров П.П.",
                "process_name": "uTorrent.exe",
                "category_name": "Запрещенный к использованию",
                "risk_level": "critical",
            }
        ])
        res3 = await process_ai_chat_query(db3, "Покажи ПК с запрещённым софтом")
        assert "запрещённого по" in res3["answer"].lower()
        assert "uTorrent.exe" in res3["answer"]

        # 4. Financial risk prompt
        db4 = AsyncMock()
        db4.execute.return_value = MockResult([
            {
                "alert_type": "license_overuse",
                "severity": "critical",
                "title": "Превышение лицензий AutoCAD",
                "financial_risk_amount": 350000.0,
                "status": "active",
            }
        ])
        res4 = await process_ai_chat_query(db4, "Какой общий финансовый риск компании?")
        assert "350,000.00 руб." in res4["answer"]
        assert "Превышение лицензий AutoCAD" in res4["answer"]

    print("PASS: All quick prompts correctly routed and answered by deterministic engine.")


if __name__ == "__main__":
    test_sql_safety()
    asyncio.run(test_openai_chat_flow_mocked())
    asyncio.run(test_openai_consultation_flow_mocked())
    asyncio.run(test_fallback_on_api_error())
    asyncio.run(test_llm_sql_failure_rolls_back_and_falls_back())
    asyncio.run(test_deterministic_routing_for_quick_prompts())
