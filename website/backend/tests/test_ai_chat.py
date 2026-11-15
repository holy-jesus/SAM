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


if __name__ == "__main__":
    test_sql_safety()
    asyncio.run(test_openai_chat_flow_mocked())
    asyncio.run(test_openai_consultation_flow_mocked())
    asyncio.run(test_fallback_on_api_error())
