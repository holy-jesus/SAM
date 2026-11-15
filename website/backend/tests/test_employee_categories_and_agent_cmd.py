import asyncio
from unittest.mock import AsyncMock, MagicMock
from sam.api.connector import enqueue_agent_command, pop_agent_commands
from sam.schemas.connector import AgentHeartbeatRequest
from sam.api.connector import receive_agent_heartbeat
from sam.models.computer import Computer


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

    def all(self):
        return self.item if isinstance(self.item, list) else [self.item]


def test_agent_command_queue():
    print("--- 1. Testing Agent Command Queue (C2) ---")
    sn = "SN-TEST-12345"
    enqueue_agent_command(sn, "scan")
    enqueue_agent_command(sn, "report")

    cmds = pop_agent_commands(sn)
    assert cmds == ["scan", "report"]
    assert pop_agent_commands(sn) == []
    print("PASS: Agent commands successfully queued and popped.")


async def test_agent_heartbeat_returns_commands():
    print("--- 2. Testing Heartbeat Picks Up Queued Commands ---")
    db = AsyncMock()
    comp = Computer(
        serial_number="SN-CMD-999",
        hostname="WS-COMMAND",
        enrollment_status="approved",
        is_online=True,
    )
    db.execute.return_value = MockResult(comp)

    enqueue_agent_command("SN-CMD-999", "scan_thorough")

    req = AgentHeartbeatRequest(serial_number="SN-CMD-999", hostname="WS-COMMAND")
    resp = await receive_agent_heartbeat(req, db=db)

    assert resp.status == "ok"
    assert resp.can_send_data is True
    assert resp.commands == ["scan_thorough"]
    print("PASS: Heartbeat correctly delivered queued command 'scan_thorough' to agent.")


if __name__ == "__main__":
    test_agent_command_queue()
    asyncio.run(test_agent_heartbeat_returns_commands())
    print("\nALL AGENT C2 AND COMMAND QUEUE TESTS PASSED SUCCESSFULLY!")
