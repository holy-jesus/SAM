import asyncio
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException
from sam.models.computer import Computer
from sam.schemas.connector import (
    AgentRegisterRequest,
    AgentReportRequest,
    AgentHeartbeatRequest,
    AgentSoftwareItem,
)
from sam.schemas.computer import ComputerEnrollmentStatusUpdate
from sam.api.connector import register_agent, receive_agent_report, receive_agent_heartbeat
from sam.api.computers import (
    get_computers,
    get_computer_enrollment_stats,
    update_computer_enrollment_status,
    approve_computer,
    block_computer,
    reset_pending_computer,
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

    def all(self):
        return self.item if isinstance(self.item, list) else [self.item]


async def test_agent_registration_flow():
    print("--- 1. Testing Agent Registration (New PC) ---")
    db = AsyncMock()
    # No existing computer
    db.execute.return_value = MockResult(None)

    req = AgentRegisterRequest(
        serial_number="PC-SERIAL-TEST-001",
        hostname="TEST-WORKSTATION",
        ip_address="192.168.1.50",
        mac_address="AA:BB:CC:DD:EE:FF",
        os_name="Windows 11 Pro",
        os_version="23H2",
        cpu="Intel Core i7-13700",
        ram_mb=32768,
    )

    auth_resp = await register_agent(req, db)
    assert auth_resp.serial_number == "PC-SERIAL-TEST-001"
    assert auth_resp.enrollment_status == "pending"
    assert auth_resp.can_send_data is False
    assert "ожидает подтверждения" in auth_resp.message
    print("PASS: New PC registered with status 'pending' and can_send_data=False")

    print("\n--- 2. Testing Report from Pending PC (Should be Rejected with 403) ---")
    pending_pc = Computer(
        id=uuid.uuid4(),
        serial_number="PC-SERIAL-TEST-001",
        hostname="TEST-WORKSTATION",
        enrollment_status="pending",
    )
    db.execute.return_value = MockResult(pending_pc)

    rep_req = AgentReportRequest(
        serial_number="PC-SERIAL-TEST-001",
        hostname="TEST-WORKSTATION",
        installed_software=[
            AgentSoftwareItem(display_name="Google Chrome", publisher="Google LLC", version="124.0")
        ],
    )
    try:
        await receive_agent_report(rep_req, db)
        assert False, "Expected HTTPException 403 for pending PC"
    except HTTPException as e:
        assert e.status_code == 403
        assert "pending" in e.detail
        print("PASS: Pending PC correctly rejected from uploading report (HTTP 403)")

    print("\n--- 3. Testing Report from Blocked PC (Should be Rejected with 403) ---")
    blocked_pc = Computer(
        id=uuid.uuid4(),
        serial_number="PC-BLOCKED-001",
        hostname="BLOCKED-HOST",
        enrollment_status="blocked",
    )
    db.execute.return_value = MockResult(blocked_pc)

    blocked_rep_req = AgentReportRequest(
        serial_number="PC-BLOCKED-001",
        hostname="BLOCKED-HOST",
        installed_software=[],
    )
    try:
        await receive_agent_report(blocked_rep_req, db)
        assert False, "Expected HTTPException 403 for blocked PC"
    except HTTPException as e:
        assert e.status_code == 403
        assert "blocked" in e.detail
        print("PASS: Blocked PC correctly rejected from uploading report (HTTP 403)")

    print("\n--- 4. Testing Heartbeat Status Responses ---")
    # Heartbeat for pending PC
    db.execute.return_value = MockResult(pending_pc)
    hb_pending = await receive_agent_heartbeat(
        AgentHeartbeatRequest(serial_number="PC-SERIAL-TEST-001"), db
    )
    assert hb_pending.recognized is True
    assert hb_pending.enrollment_status == "pending"
    assert hb_pending.can_send_data is False
    print("PASS: Heartbeat for pending PC reports can_send_data=False")

    # Heartbeat for approved PC
    approved_pc = Computer(
        id=uuid.uuid4(),
        serial_number="PC-APPROVED-001",
        hostname="APPROVED-HOST",
        enrollment_status="approved",
        installed_software=[],
    )
    db.execute.return_value = MockResult(approved_pc)
    hb_approved = await receive_agent_heartbeat(
        AgentHeartbeatRequest(serial_number="PC-APPROVED-001"), db
    )
    assert hb_approved.recognized is True
    assert hb_approved.enrollment_status == "approved"
    assert hb_approved.can_send_data is True
    print("PASS: Heartbeat for approved PC reports can_send_data=True")

    print("\n--- 5. Testing Admin Approval and Blocking Endpoints ---")
    pc_id_str = str(pending_pc.id)
    db.execute.return_value = MockResult(pending_pc)

    # Approve
    approved_res = await approve_computer(pc_id_str, db)
    assert pending_pc.enrollment_status == "approved"
    assert approved_res["enrollment_status"] == "approved"
    print("PASS: Computer approved successfully via POST /approve")

    # Block
    block_res = await block_computer(pc_id_str, db)
    assert pending_pc.enrollment_status == "blocked"
    assert block_res["enrollment_status"] == "blocked"
    print("PASS: Computer blocked successfully via POST /block")

    # Reset to pending
    reset_res = await reset_pending_computer(pc_id_str, db)
    assert pending_pc.enrollment_status == "pending"
    assert reset_res["enrollment_status"] == "pending"
    print("PASS: Computer reset to pending via POST /reset-pending")

    # Status update via PATCH
    patch_res = await update_computer_enrollment_status(
        pc_id_str, ComputerEnrollmentStatusUpdate(status="approved"), db
    )
    assert pending_pc.enrollment_status == "approved"
    assert patch_res["enrollment_status"] == "approved"
    print("PASS: Computer status updated via PATCH /status")

    # Invalid status validation
    try:
        await update_computer_enrollment_status(
            pc_id_str, ComputerEnrollmentStatusUpdate(status="invalid_status"), db
        )
        assert False, "Expected 400 for invalid status"
    except HTTPException as e:
        assert e.status_code == 400
        print("PASS: Invalid enrollment status rejected with HTTP 400")

    print("\n--- 6. Testing Enrollment Stats Endpoint ---")
    # Mock group_by counts
    db.execute.return_value = MockResult([
        ("approved", 8),
        ("pending", 3),
        ("blocked", 2),
    ])
    stats = await get_computer_enrollment_stats(db)
    assert stats.total == 13
    assert stats.approved == 8
    assert stats.pending == 3
    assert stats.blocked == 2
    print("PASS: Enrollment stats correctly aggregates total=13, approved=8, pending=3, blocked=2")

    print("\nALL ENROLLMENT TESTS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    asyncio.run(test_agent_registration_flow())
