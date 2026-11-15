import uuid
from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sam.db import get_db
from sam.models.computer import Computer
from sam.models.installed_software import InstalledSoftware
from sam.models.import_history import ImportHistory
from sam.schemas.connector import (
    AgentReportRequest,
    AgentHeartbeatRequest,
    AgentRegisterRequest,
    AgentAuthResponse,
    AgentHeartbeatResponse,
    ImportResultResponse,
    ImportHistoryResponse,
)
from sam.services.matcher import match_raw_process_to_catalog
from sam.services.dump_parser import parse_dump_file
from sam.services.compliance_engine import recalculate_compliance_alerts
from sam.services.substitution_service import (
    enqueue_software_substitution_check,
    is_official_software_name,
)

router = APIRouter(prefix="/connector", tags=["Agent Connector & Dump Import"])


@router.post("/agent/register", response_model=AgentAuthResponse)
async def register_agent(payload: AgentRegisterRequest, db: AsyncSession = Depends(get_db)):
    """
    Первичная регистрация клиента при установке/первом запуске.
    Если ПК новый, он добавляется со статусом 'pending' (заявка).
    Если ПК уже зарегистрирован, обновляются его параметры и возвращается текущий статус.
    """
    comp_res = await db.execute(
        select(Computer).where(Computer.serial_number == payload.serial_number.strip())
    )
    comp = comp_res.scalar_one_or_none()
    now = datetime.now(timezone.utc)

    if not comp:
        comp = Computer(
            serial_number=payload.serial_number.strip(),
            hostname=payload.hostname.strip(),
            ip_address=payload.ip_address,
            mac_address=payload.mac_address,
            os_name=payload.os_name,
            os_version=payload.os_version,
            cpu_info=payload.cpu,
            ram_mb=payload.ram_mb,
            enrollment_status="pending",
            is_online=True,
            last_seen_at=now,
        )
        db.add(comp)
        await db.commit()
        await db.refresh(comp)

        return AgentAuthResponse(
            serial_number=comp.serial_number,
            hostname=comp.hostname,
            enrollment_status="pending",
            can_send_data=False,
            message="Заявка на добавление ПК принята и ожидает подтверждения администратором.",
            server_time=now,
        )

    # Updating computer hardware info
    comp.hostname = payload.hostname.strip()
    if payload.ip_address:
        comp.ip_address = payload.ip_address
    if payload.mac_address:
        comp.mac_address = payload.mac_address
    if payload.os_name:
        comp.os_name = payload.os_name
    if payload.os_version:
        comp.os_version = payload.os_version
    if payload.cpu:
        comp.cpu_info = payload.cpu
    if payload.ram_mb:
        comp.ram_mb = payload.ram_mb
    comp.is_online = True
    comp.last_seen_at = now
    await db.commit()
    await db.refresh(comp)

    can_send = (comp.enrollment_status == "approved")
    if comp.enrollment_status == "approved":
        msg = "ПК авторизован. Приём данных разрешён."
    elif comp.enrollment_status == "blocked":
        msg = "ПК заблокирован администратором (в чёрном списке). Отправка данных запрещена."
    else:
        msg = "Заявка на добавление ПК ожидает подтверждения администратором."

    return AgentAuthResponse(
        serial_number=comp.serial_number,
        hostname=comp.hostname,
        enrollment_status=comp.enrollment_status,
        can_send_data=can_send,
        message=msg,
        server_time=now,
    )


@router.post("/agent/report")
async def receive_agent_report(payload: AgentReportRequest, db: AsyncSession = Depends(get_db)):
    # 1. Find or create computer
    comp_res = await db.execute(
        select(Computer).where(Computer.serial_number == payload.serial_number.strip())
    )
    comp = comp_res.scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if not comp:
        comp = Computer(
            serial_number=payload.serial_number.strip(),
            hostname=payload.hostname.strip(),
            ip_address=payload.ip_address,
            mac_address=payload.mac_address,
            os_name=payload.os_name,
            os_version=payload.os_version,
            cpu_info=payload.cpu,
            ram_mb=payload.ram_mb,
            enrollment_status="pending",
            is_online=True,
            last_seen_at=now,
        )
        db.add(comp)
        await db.commit()
        raise HTTPException(
            status_code=403,
            detail="ПК не авторизован (создана заявка со статусом 'pending'). Приём данных отклонён до подтверждения администратором.",
        )

    # Check enrollment status
    if comp.enrollment_status == "pending":
        comp.hostname = payload.hostname.strip()
        comp.is_online = True
        comp.last_seen_at = now
        await db.commit()
        raise HTTPException(
            status_code=403,
            detail="Заявка на подключение данного ПК ожидает подтверждения администратором (статус: pending). Отправка данных отклонена.",
        )
    elif comp.enrollment_status == "blocked":
        comp.hostname = payload.hostname.strip()
        comp.is_online = True
        comp.last_seen_at = now
        await db.commit()
        raise HTTPException(
            status_code=403,
            detail="Данный ПК заблокирован администратором (статус: blocked / чёрный список). Приём данных отклонён.",
        )
    elif comp.enrollment_status != "approved":
        raise HTTPException(
            status_code=403,
            detail=f"Недопустимый статус авторизации ПК: '{comp.enrollment_status}'. Приём данных отклонён.",
        )

    comp.hostname = payload.hostname.strip()
    if payload.ip_address:
        comp.ip_address = payload.ip_address
    if payload.mac_address:
        comp.mac_address = payload.mac_address
    if payload.os_name:
        comp.os_name = payload.os_name
    if payload.os_version:
        comp.os_version = payload.os_version
    if payload.cpu:
        comp.cpu_info = payload.cpu
    if payload.ram_mb:
        comp.ram_mb = payload.ram_mb
    comp.is_online = True
    comp.last_seen_at = now

    # 2. Process software items
    matched_count = 0
    for sw in payload.installed_software:
        # Match with catalog using Hash -> Path Heuristics -> RU Registry -> Embeddings -> Wikimedia -> OpenAI
        match_res = await match_raw_process_to_catalog(
            db=db,
            raw_process_name=sw.display_name,
            binary_hash=sw.binary_hash,
            publisher=sw.publisher,
            install_path=sw.install_path,
            reported_version=sw.version,
        )
        cat_id = match_res.get("matched_catalog_software_id")
        category_id = match_res.get("category_id") or 1
        conf = match_res.get("confidence", 0.0)
        if conf >= 0.70:
            matched_count += 1

        # Автоматическая очередь проверки импортозамещения для распознанного зарубежного ПО
        matched_official = match_res.get("matched_name") or sw.display_name
        if match_res.get("match_source") != "ru_registry" and is_official_software_name(matched_official):
            enqueue_software_substitution_check(
                matched_official,
                catalog_software_id=uuid.UUID(cat_id) if cat_id else None,
            )

        # Check existing install
        existing_inst_res = await db.execute(
            select(InstalledSoftware).where(
                and_(
                    InstalledSoftware.computer_id == comp.id,
                    InstalledSoftware.raw_display_name == sw.display_name,
                )
            )
        )
        existing_inst = existing_inst_res.scalar_one_or_none()

        launch_time = sw.last_launched_at or now

        if existing_inst:
            existing_inst.raw_publisher = sw.publisher
            existing_inst.raw_version = sw.version
            existing_inst.install_path = sw.install_path
            existing_inst.binary_hash = sw.binary_hash
            existing_inst.last_launched_at = launch_time
            existing_inst.last_seen_at = now
            existing_inst.is_deleted = False
            if not existing_inst.is_verified_by_admin:
                existing_inst.catalog_software_id = uuid.UUID(cat_id) if cat_id else None
                existing_inst.category_id = category_id
                existing_inst.match_confidence = conf
        else:
            new_inst = InstalledSoftware(
                computer_id=comp.id,
                raw_display_name=sw.display_name,
                raw_publisher=sw.publisher,
                raw_version=sw.version,
                install_path=sw.install_path,
                binary_hash=sw.binary_hash,
                last_launched_at=launch_time,
                source="agent",
                catalog_software_id=uuid.UUID(cat_id) if cat_id else None,
                category_id=category_id,
                match_confidence=conf,
                is_verified_by_admin=conf >= 0.90,
                last_seen_at=now,
            )
            db.add(new_inst)

    await db.commit()

    # Recalculate compliance alerts
    await recalculate_compliance_alerts(db)

    return {
        "success": True,
        "computer_id": str(comp.id),
        "total_software_reported": len(payload.installed_software),
        "matched_count": matched_count,
    }


@router.post("/agent/heartbeat", response_model=AgentHeartbeatResponse)
async def receive_agent_heartbeat(
    payload: AgentHeartbeatRequest, db: AsyncSession = Depends(get_db)
):
    comp_res = await db.execute(
        select(Computer).where(Computer.serial_number == payload.serial_number.strip())
    )
    comp = comp_res.scalar_one_or_none()
    if comp:
        comp.is_online = True
        comp.last_seen_at = datetime.now(timezone.utc)
        if payload.hostname:
            comp.hostname = payload.hostname.strip()
        await db.commit()

        can_send = comp.enrollment_status == "approved"
        if comp.enrollment_status == "approved":
            msg = "ПК авторизован. Приём данных разрешён."
        elif comp.enrollment_status == "blocked":
            msg = "ПК заблокирован администратором (в чёрном списке)."
        else:
            msg = "Заявка ожидает подтверждения администратором."

        return AgentHeartbeatResponse(
            status="ok",
            recognized=True,
            enrollment_status=comp.enrollment_status,
            can_send_data=can_send,
            message=msg,
        )

    return AgentHeartbeatResponse(
        status="ok",
        recognized=False,
        enrollment_status="unregistered",
        can_send_data=False,
        message="ПК не зарегистрирован на сервере",
    )


@router.post("/import/upload", response_model=ImportResultResponse)
async def upload_dump_file(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Загружен пустой файл")

    rows = parse_dump_file(file.filename or "dump.csv", content)
    if not rows:
        raise HTTPException(
            status_code=400,
            detail="Не удалось распознать формат строк дампа. Проверьте заголовки COMPUTERS.SERIAL_NUMBER и SOFTWARE.DISPLAYNAME",
        )

    # Cache computers
    all_comps = (await db.execute(select(Computer))).scalars().all()
    computers_by_serial = {c.serial_number: c for c in all_comps}
    affected_serials = set()

    now = datetime.now(timezone.utc)
    imported_count = 0
    matched_automatically = 0

    for r in rows:
        sn = r.get("serial_number", "").strip()
        display_name = r.get("display_name", "").strip()
        if not sn or not display_name:
            continue

        affected_serials.add(sn)

        if sn not in computers_by_serial:
            new_comp = Computer(
                serial_number=sn,
                hostname=f"HOST-{sn}",
                ip_address="192.168.1.100",
                os_name="Windows 11 Pro",
                os_version="23H2",
                cpu_info="Intel Core i5",
                ram_mb=16384,
                is_online=True,
                enrollment_status="approved",
                last_seen_at=now,
            )
            db.add(new_comp)
            await db.flush()
            computers_by_serial[sn] = new_comp

        comp = computers_by_serial[sn]
        publisher = r.get("publisher", "").strip()
        version = r.get("version", "").strip()
        binary_hash = r.get("binary_hash", "").strip() or None
        install_path = r.get("install_path", "").strip() or None

        # Match software using Hash -> Path Heuristics -> RU Registry -> Embeddings -> Wikimedia -> OpenAI
        match_res = await match_raw_process_to_catalog(
            db=db,
            raw_process_name=display_name,
            binary_hash=binary_hash,
            publisher=publisher,
            install_path=install_path,
            reported_version=version,
        )
        cat_id = match_res.get("matched_catalog_software_id")
        category_id = match_res.get("category_id") or 1
        conf = match_res.get("confidence", 0.0)
        if conf >= 0.70:
            matched_automatically += 1

        # Автоматическая очередь проверки импортозамещения для распознанного зарубежного ПО
        matched_official = match_res.get("matched_name") or display_name
        if match_res.get("match_source") != "ru_registry" and is_official_software_name(matched_official):
            enqueue_software_substitution_check(
                matched_official,
                catalog_software_id=uuid.UUID(cat_id) if cat_id else None,
            )

        inst = InstalledSoftware(
            computer_id=comp.id,
            raw_display_name=display_name,
            raw_publisher=publisher,
            raw_version=version,
            install_path=install_path,
            binary_hash=binary_hash,
            source="automatic",
            catalog_software_id=uuid.UUID(cat_id) if cat_id else None,
            category_id=category_id,
            match_confidence=conf,
            is_verified_by_admin=conf >= 0.90,
            last_launched_at=now,
            last_seen_at=now,
        )
        db.add(inst)
        imported_count += 1

    # Save import history
    history = ImportHistory(
        filename=file.filename or "uploaded_dump",
        total_rows=len(rows),
        computers_affected=len(affected_serials),
        software_rows_imported=imported_count,
        matched_automatically=matched_automatically,
        status="success",
    )
    db.add(history)
    await db.commit()

    # Recalculate compliance alerts after import
    await recalculate_compliance_alerts(db)

    return {
        "filename": file.filename or "uploaded_dump",
        "total_rows": len(rows),
        "computers_affected": len(affected_serials),
        "software_rows_imported": imported_count,
        "matched_automatically": matched_automatically,
    }


@router.get("/import/history", response_model=List[ImportHistoryResponse])
async def get_import_history(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ImportHistory).order_by(ImportHistory.created_at.desc())
    )
    items = result.scalars().all()
    return items
