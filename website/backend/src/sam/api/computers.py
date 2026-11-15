import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sam.db import get_db
from sam.models.computer import Computer
from sam.models.employee import Employee
from sam.models.catalog import SoftwareCatalog
from sam.models.installed_software import InstalledSoftware
from sam.schemas.computer import (
    ComputerCreate,
    ComputerUpdate,
    ComputerResponse,
    ComputerEnrollmentStatusUpdate,
    ComputerEnrollmentStatsResponse,
)
from sam.schemas.installed_software import (
    InstalledSoftwareResponse,
    InstalledSoftwareManualCreate,
)
from sam.api.connector import enqueue_agent_command

router = APIRouter(prefix="/computers", tags=["Computers"])


def _serialize_computer(c: Computer) -> dict:
    installed = []
    if c.installed_software:
        for s in c.installed_software:
            installed.append({
                "id": str(s.id),
                "computer_id": str(c.id),
                "computer_hostname": c.hostname,
                "computer_serial": c.serial_number,
                "raw_display_name": s.raw_display_name,
                "raw_publisher": s.raw_publisher,
                "raw_version": s.raw_version,
                "install_path": s.install_path,
                "binary_hash": s.binary_hash,
                "last_launched_at": s.last_launched_at,
                "source": s.source,
                "catalog_software_id": str(s.catalog_software_id) if s.catalog_software_id else None,
                "catalog_software_name": s.catalog_software.name if s.catalog_software else None,
                "category_id": s.category_id,
                "category_name": s.category.name if s.category else None,
                "is_problematic": s.category.is_problematic if s.category else False,
                "match_confidence": s.match_confidence,
                "is_verified_by_admin": s.is_verified_by_admin,
                "is_deleted": s.is_deleted,
                "first_seen_at": s.first_seen_at,
                "last_seen_at": s.last_seen_at,
            })

    emp = None
    if c.employee:
        emp = {
            "id": str(c.employee.id),
            "full_name": c.employee.full_name,
            "email": c.employee.email,
            "department": c.employee.department,
            "position": c.employee.position,
            "status": c.employee.status,
        }

    return {
        "id": str(c.id),
        "serial_number": c.serial_number,
        "hostname": c.hostname,
        "ip_address": c.ip_address,
        "mac_address": c.mac_address,
        "os_name": c.os_name,
        "os_version": c.os_version,
        "cpu_info": c.cpu_info,
        "ram_mb": c.ram_mb,
        "disk_info": c.disk_info,
        "is_online": c.is_online,
        "enrollment_status": c.enrollment_status or "pending",
        "last_seen_at": c.last_seen_at,
        "employee_id": str(c.employee_id) if c.employee_id else None,
        "employee": emp,
        "installed_count": len(c.installed_software) if c.installed_software else 0,
        "installed_software": installed,
        "created_at": c.created_at,
        "updated_at": c.updated_at,
    }


@router.get("", response_model=List[ComputerResponse])
async def get_computers(
    search: Optional[str] = Query(None),
    is_online: Optional[bool] = Query(None),
    status: Optional[str] = Query(
        None, description="Фильтр по статусу авторизации: pending, approved, blocked"
    ),
    enrollment_status: Optional[str] = Query(
        None, description="Синоним status: pending, approved, blocked"
    ),
    db: AsyncSession = Depends(get_db),
):
    query = select(Computer)
    conditions = []

    if search:
        s = f"%{search.strip().lower()}%"
        conditions.append(
            or_(
                func.lower(Computer.hostname).like(s),
                func.lower(Computer.serial_number).like(s),
                func.lower(Computer.ip_address).like(s),
            )
        )

    if is_online is not None:
        conditions.append(Computer.is_online == is_online)

    target_status = status or enrollment_status
    if target_status:
        target_status = target_status.strip().lower()
        conditions.append(Computer.enrollment_status == target_status)

    if conditions:
        query = query.where(and_(*conditions))

    query = query.order_by(Computer.hostname.asc())
    result = await db.execute(query)
    computers = result.scalars().all()

    return [_serialize_computer(c) for c in computers]


@router.get("/enrollment/stats", response_model=ComputerEnrollmentStatsResponse)
async def get_computer_enrollment_stats(db: AsyncSession = Depends(get_db)):
    """
    Возвращает статистику по статусам авторизации ПК:
    общее число, количество заявок (pending), разрешённых (approved) и заблокированных (blocked).
    """
    rows = await db.execute(
        select(Computer.enrollment_status, func.count(Computer.id)).group_by(Computer.enrollment_status)
    )
    counts = {r[0]: r[1] for r in rows.all()}
    pending = counts.get("pending", 0)
    approved = counts.get("approved", 0)
    blocked = counts.get("blocked", 0)
    total = sum(counts.values())
    return ComputerEnrollmentStatsResponse(
        total=total,
        pending=pending,
        approved=approved,
        blocked=blocked,
    )


@router.post("", response_model=ComputerResponse)
async def create_computer(payload: ComputerCreate, db: AsyncSession = Depends(get_db)):
    # Check if serial number already exists
    existing = await db.execute(
        select(Computer).where(Computer.serial_number == payload.serial_number.strip())
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Компьютер с таким серийным номером уже существует")

    emp_id = uuid.UUID(payload.employee_id) if payload.employee_id else None

    comp = Computer(
        serial_number=payload.serial_number.strip(),
        hostname=payload.hostname.strip(),
        ip_address=payload.ip_address,
        mac_address=payload.mac_address,
        os_name=payload.os_name,
        os_version=payload.os_version,
        cpu_info=payload.cpu_info,
        ram_mb=payload.ram_mb,
        disk_info=payload.disk_info,
        is_online=payload.is_online,
        enrollment_status=payload.enrollment_status or "approved",
        employee_id=emp_id,
        last_seen_at=datetime.now(timezone.utc),
    )
    db.add(comp)
    await db.commit()
    await db.refresh(comp)

    return _serialize_computer(comp)


@router.get("/{computer_id}", response_model=ComputerResponse)
async def get_computer(computer_id: str, db: AsyncSession = Depends(get_db)):
    try:
        cid = uuid.UUID(computer_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат UUID")

    result = await db.execute(select(Computer).where(Computer.id == cid))
    comp = result.scalar_one_or_none()
    if not comp:
        raise HTTPException(status_code=404, detail="Компьютер не найден")

    return _serialize_computer(comp)


@router.put("/{computer_id}", response_model=ComputerResponse)
async def update_computer(
    computer_id: str, payload: ComputerUpdate, db: AsyncSession = Depends(get_db)
):
    try:
        cid = uuid.UUID(computer_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат UUID")

    result = await db.execute(select(Computer).where(Computer.id == cid))
    comp = result.scalar_one_or_none()
    if not comp:
        raise HTTPException(status_code=404, detail="Компьютер не найден")

    update_data = payload.model_dump(exclude_unset=True)
    if "employee_id" in update_data:
        raw_emp_id = update_data.pop("employee_id")
        comp.employee_id = uuid.UUID(raw_emp_id) if raw_emp_id else None

    for field, value in update_data.items():
        setattr(comp, field, value)

    await db.commit()
    await db.refresh(comp)
    return _serialize_computer(comp)


@router.patch("/{computer_id}/status", response_model=ComputerResponse)
async def update_computer_enrollment_status(
    computer_id: str,
    payload: ComputerEnrollmentStatusUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    Изменение статуса авторизации ПК:
    - 'pending' — заявка на добавление
    - 'approved' — разрешён (данные принимаются)
    - 'blocked' — чёрный список (запросы отклоняются)
    """
    try:
        cid = uuid.UUID(computer_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат UUID")

    target_status = payload.status.strip().lower()
    if target_status not in ("pending", "approved", "blocked"):
        raise HTTPException(
            status_code=400,
            detail=f"Недопустимый статус '{payload.status}'. Разрешённые: 'pending', 'approved', 'blocked'.",
        )

    result = await db.execute(select(Computer).where(Computer.id == cid))
    comp = result.scalar_one_or_none()
    if not comp:
        raise HTTPException(status_code=404, detail="Компьютер не найден")

    comp.enrollment_status = target_status
    await db.commit()
    await db.refresh(comp)
    return _serialize_computer(comp)


@router.post("/{computer_id}/approve", response_model=ComputerResponse)
async def approve_computer(computer_id: str, db: AsyncSession = Depends(get_db)):
    """
    Одобрить ПК (перевести в статус 'approved'). Приём данных от агента разрешается.
    """
    try:
        cid = uuid.UUID(computer_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат UUID")

    result = await db.execute(select(Computer).where(Computer.id == cid))
    comp = result.scalar_one_or_none()
    if not comp:
        raise HTTPException(status_code=404, detail="Компьютер не найден")

    comp.enrollment_status = "approved"
    await db.commit()
    await db.refresh(comp)
    return _serialize_computer(comp)


@router.post("/{computer_id}/block", response_model=ComputerResponse)
async def block_computer(computer_id: str, db: AsyncSession = Depends(get_db)):
    """
    Отклонить/заблокировать ПК (перевести в статус 'blocked' / чёрный список).
    Приём данных от агента отклоняется с ошибкой 403 Forbidden.
    """
    try:
        cid = uuid.UUID(computer_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат UUID")

    result = await db.execute(select(Computer).where(Computer.id == cid))
    comp = result.scalar_one_or_none()
    if not comp:
        raise HTTPException(status_code=404, detail="Компьютер не найден")

    comp.enrollment_status = "blocked"
    await db.commit()
    await db.refresh(comp)
    return _serialize_computer(comp)


@router.post("/{computer_id}/reset-pending", response_model=ComputerResponse)
async def reset_pending_computer(computer_id: str, db: AsyncSession = Depends(get_db)):
    """
    Вернуть ПК в статус рассмотрения заявки ('pending').
    """
    try:
        cid = uuid.UUID(computer_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат UUID")

    result = await db.execute(select(Computer).where(Computer.id == cid))
    comp = result.scalar_one_or_none()
    if not comp:
        raise HTTPException(status_code=404, detail="Компьютер не найден")

    comp.enrollment_status = "pending"
    await db.commit()
    await db.refresh(comp)
    return _serialize_computer(comp)



@router.delete("/{computer_id}")
async def delete_computer(computer_id: str, db: AsyncSession = Depends(get_db)):
    try:
        cid = uuid.UUID(computer_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат UUID")

    result = await db.execute(select(Computer).where(Computer.id == cid))
    comp = result.scalar_one_or_none()
    if not comp:
        raise HTTPException(status_code=404, detail="Компьютер не найден")

    await db.delete(comp)
    await db.commit()
    return {"success": True}


@router.post("/{computer_id}/software", response_model=InstalledSoftwareResponse)
async def add_software_to_computer(
    computer_id: str,
    payload: InstalledSoftwareManualCreate,
    db: AsyncSession = Depends(get_db),
):
    try:
        cid = uuid.UUID(computer_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат UUID компьютера")

    result = await db.execute(select(Computer).where(Computer.id == cid))
    comp = result.scalar_one_or_none()
    if not comp:
        raise HTTPException(status_code=404, detail="Компьютер не найден")

    cat_software = None
    if payload.catalog_software_id:
        cat_res = await db.execute(
            select(SoftwareCatalog).where(SoftwareCatalog.id == uuid.UUID(payload.catalog_software_id))
        )
        cat_software = cat_res.scalar_one_or_none()

    display_name = payload.raw_display_name or (cat_software.name if cat_software else "Ручная установка")
    publisher = payload.raw_publisher or (cat_software.vendor if cat_software else "")
    category_id = cat_software.category_id if cat_software else 1

    inst = InstalledSoftware(
        computer_id=comp.id,
        raw_display_name=display_name,
        raw_publisher=publisher,
        raw_version=payload.raw_version or "1.0",
        install_path=payload.install_path or "C:\\Program Files\\Manual",
        source="manual",
        catalog_software_id=cat_software.id if cat_software else None,
        category_id=category_id,
        match_confidence=1.0,
        is_verified_by_admin=True,
        last_launched_at=payload.last_launched_at or datetime.now(timezone.utc),
    )
    db.add(inst)
    await db.commit()
    await db.refresh(inst)

    return {
        "id": str(inst.id),
        "computer_id": str(comp.id),
        "computer_hostname": comp.hostname,
        "computer_serial": comp.serial_number,
        "raw_display_name": inst.raw_display_name,
        "raw_publisher": inst.raw_publisher,
        "raw_version": inst.raw_version,
        "install_path": inst.install_path,
        "binary_hash": inst.binary_hash,
        "last_launched_at": inst.last_launched_at,
        "source": inst.source,
        "catalog_software_id": str(cat_software.id) if cat_software else None,
        "catalog_software_name": cat_software.name if cat_software else None,
        "category_id": inst.category_id,
        "category_name": inst.category.name if inst.category else None,
        "is_problematic": inst.category.is_problematic if inst.category else False,
        "match_confidence": inst.match_confidence,
        "is_verified_by_admin": inst.is_verified_by_admin,
        "is_deleted": inst.is_deleted,
        "first_seen_at": inst.first_seen_at,
        "last_seen_at": inst.last_seen_at,
    }


@router.delete("/{computer_id}/software/{installed_software_id}")
async def remove_software_from_computer(
    computer_id: str,
    installed_software_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        inst_id = uuid.UUID(installed_software_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат UUID инсталляции")

    result = await db.execute(
        select(InstalledSoftware).where(InstalledSoftware.id == inst_id)
    )
    inst = result.scalar_one_or_none()
    if not inst:
        raise HTTPException(status_code=404, detail="Запись об установленном ПО не найдена")

    await db.delete(inst)
    await db.commit()
    return {"success": True}


@router.post("/{computer_id}/scan")
async def trigger_computer_scan(
    computer_id: str,
    thorough: bool = Query(False, description="Запустить тщательное сканирование диска"),
    db: AsyncSession = Depends(get_db),
):
    """
    Отправляет команду на запуск удалённого сканирования ПО на агенте хоста.
    Если агент онлайн по IP-адресу, запрос отправляется напрямую на порт 8765.
    Команда также ставится в очередь Command & Control для следующего heartbeat.
    """
    try:
        cid = uuid.UUID(computer_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат UUID")

    result = await db.execute(select(Computer).where(Computer.id == cid))
    comp = result.scalar_one_or_none()
    if not comp:
        raise HTTPException(status_code=404, detail="Компьютер не найден")

    # 1. Постановка команды в очередь для heartbeat
    cmd = "scan_thorough" if thorough else "scan"
    enqueue_agent_command(comp.serial_number, cmd)

    # 2. Попытка прямого вызова API агента, если указан IP
    direct_triggered = False
    direct_message = None
    if comp.ip_address:
        try:
            import httpx
            agent_url = f"http://{comp.ip_address}:8765/api/v1/scan"
            async with httpx.AsyncClient(timeout=2.5) as client:
                resp = await client.post(agent_url, json={"thorough": thorough})
                if resp.status_code in (200, 202):
                    direct_triggered = True
                    direct_message = "Команда сканирования немедленно принята агентом по сети."
        except Exception:
            pass

    msg = direct_message or (
        f"Команда '{cmd}' добавлена в очередь C2 и будет исполнена агентом {comp.hostname} при следующем heartbeat."
    )
    return {
        "success": True,
        "computer_id": str(comp.id),
        "hostname": comp.hostname,
        "command": cmd,
        "direct_triggered": direct_triggered,
        "message": msg,
    }


@router.get("/{computer_id}/agent-status")
async def get_computer_agent_status(
    computer_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Опрашивает статус локального агента на рабочей станции по порту 8765.
    """
    try:
        cid = uuid.UUID(computer_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат UUID")

    result = await db.execute(select(Computer).where(Computer.id == cid))
    comp = result.scalar_one_or_none()
    if not comp:
        raise HTTPException(status_code=404, detail="Компьютер не найден")

    if not comp.ip_address:
        return {
            "online": False,
            "agent_reachable": False,
            "message": "У компьютера отсутствует IP-адрес",
        }

    try:
        import httpx
        agent_url = f"http://{comp.ip_address}:8765/api/v1/status"
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(agent_url)
            if resp.status_code == 200:
                return {
                    "online": True,
                    "agent_reachable": True,
                    "agent_data": resp.json(),
                }
    except Exception as e:
        pass

    return {
        "online": comp.is_online,
        "agent_reachable": False,
        "last_seen_at": comp.last_seen_at,
        "message": f"Агент на {comp.ip_address}:8765 не ответил напрямую (используется фоновый статус)",
    }

