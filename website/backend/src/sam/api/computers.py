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
)
from sam.schemas.installed_software import (
    InstalledSoftwareResponse,
    InstalledSoftwareManualCreate,
)

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

    if conditions:
        query = query.where(and_(*conditions))

    query = query.order_by(Computer.hostname.asc())
    result = await db.execute(query)
    computers = result.scalars().all()

    return [_serialize_computer(c) for c in computers]


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
