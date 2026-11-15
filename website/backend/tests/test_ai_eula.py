import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from sam.services.ai_eula import (
    analyze_eula_text,
    _fallback_deterministic_eula_analysis,
    _run_eula_analysis_with_openai,
    get_openai_client,
)


def test_ai_eula_deterministic_non_commercial():
    print("--- 1. Testing Deterministic EULA Analysis (Non-commercial restriction) ---")
    eula = """
    END USER LICENSE AGREEMENT
    This software is licensed for personal, non-commercial use only.
    Any commercial or business use in an enterprise organization is strictly prohibited.
    Reverse engineering, decompilation, and disassembly are prohibited.
    """
    res = _fallback_deterministic_eula_analysis(eula)
    assert res["commercial_use_allowed"] is False
    assert res["risk_level"] == "critical"
    assert any("некоммерческ" in r.lower() or "personal" in r.lower() for r in res["key_restrictions"])
    assert "КРИТИЧЕСКИЙ РИСК" in res["summary_ru"]
    print("PASS: Non-commercial EULA correctly flagged as critical risk.")


def test_ai_eula_deterministic_commercial_auto_renew_trial():
    print("--- 2. Testing Deterministic EULA Analysis (Commercial with auto-renewal and trial) ---")
    eula = """
    CORPORATE LICENSE AGREEMENT
    Commercial use is permitted for business purposes.
    Subscription will auto-renew annually and recurring billing applies unless cancelled.
    Includes a 30-day free trial period.
    """
    res = _fallback_deterministic_eula_analysis(eula)
    assert res["commercial_use_allowed"] is True
    assert res["has_auto_renewal"] is True
    assert res["trial_period_days"] == 30
    assert res["risk_level"] in ("medium", "high")
    print("PASS: Commercial EULA with auto-renewal and trial correctly parsed.")


async def test_ai_eula_with_mocked_openai():
    print("--- 3. Testing Real OpenAI Pipeline with Mocked API Responses ---")
    mock_client = AsyncMock()

    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps({
        "commercial_use_allowed": False,
        "risk_level": "critical",
        "has_auto_renewal": True,
        "trial_period_days": 14,
        "key_restrictions": [
            "Использование строго ограничено некоммерческими целями",
            "Автоматическое списание подписки через 14 дней",
            "Запрет модификации и обратной разработки"
        ],
        "summary_ru": "### Юридическое заключение\nОбнаружен **критический риск**: лицензия запрещает коммерческое использование."
    })
    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]

    mock_client.chat.completions.create.return_value = mock_resp

    with patch("sam.services.ai_eula.get_openai_client", return_value=mock_client):
        sample_eula = "Personal use only. 14-day trial with auto-renewal."
        res = await analyze_eula_text(sample_eula)

        assert res["commercial_use_allowed"] is False
        assert res["risk_level"] == "critical"
        assert res["has_auto_renewal"] is True
        assert res["trial_period_days"] == 14
        assert len(res["key_restrictions"]) == 3
        assert "критический риск" in res["summary_ru"].lower()
        assert mock_client.chat.completions.create.called

    print("PASS: OpenAI EULA pipeline executed cleanly and parsed JSON.")


async def test_ai_eula_fallback_on_openai_error():
    print("--- 4. Testing Fallback to Deterministic Engine on API Exception ---")
    mock_client = AsyncMock()
    mock_client.chat.completions.create.side_effect = Exception("OpenAI API Connection Timeout (DNS failed)")

    with patch("sam.services.ai_eula.get_openai_client", return_value=mock_client):
        eula_sample = "This software is for personal use only."
        res = await analyze_eula_text(eula_sample)

        assert res["commercial_use_allowed"] is False
        assert res["risk_level"] == "critical"
        assert "КРИТИЧЕСКИЙ РИСК" in res["summary_ru"]

    print("PASS: Fallback to deterministic EULA analysis on OpenAI exception succeeded without error.")


if __name__ == "__main__":
    test_ai_eula_deterministic_non_commercial()
    test_ai_eula_deterministic_commercial_auto_renew_trial()
    asyncio.run(test_ai_eula_with_mocked_openai())
    asyncio.run(test_ai_eula_fallback_on_openai_error())
    print("\nALL AI EULA TESTS PASSED SUCCESSFULLY!")
