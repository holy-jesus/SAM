import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sam.db import get_db
from sam.models.employee import Employee
from sam.models.computer import Computer
from sam.schemas.employee import (
    EmployeeCreate,
    EmployeeUpdate,
    EmployeeResponse,
    EmployeeDetailResponse,
)

router = APIRouter(prefix="/employees", tags=["Employees"])


@router.get("", response_model=List[EmployeeResponse])
async def get_employees(
    search: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
):
    query = select(Employee)
    conditions = []

    if search:
        s = f"%{search.strip().lower()}%"
        conditions.append(
            or_(
                func.lower(Employee.full_name).like(s),
                func.lower(Employee.email).like(s),
                func.lower(Employee.department).like(s),
            )
        )

    if department and department != "all":
        conditions.append(Employee.department == department)

    if status_filter and status_filter != "all":
        conditions.append(Employee.status == status_filter)

    if conditions:
        query = query.where(and_(*conditions))

    query = query.order_by(Employee.full_name.asc())
    result = await db.execute(query)
    employees = result.scalars().all()

    out = []
    for emp in employees:
        out.append({
            "id": str(emp.id),
            "full_name": emp.full_name,
            "email": emp.email,
            "department": emp.department,
            "position": emp.position,
            "status": emp.status,
            "computers_count": len(emp.computers) if emp.computers else 0,
            "created_at": emp.created_at,
            "updated_at": emp.updated_at,
        })
    return out


@router.post("", response_model=EmployeeResponse)
async def create_employee(payload: EmployeeCreate, db: AsyncSession = Depends(get_db)):
    emp = Employee(
        full_name=payload.full_name.strip(),
        email=payload.email.strip() if payload.email else None,
        department=payload.department,
        position=payload.position,
        status=payload.status or "active",
    )
    db.add(emp)
    await db.commit()
    await db.refresh(emp)

    return {
        "id": str(emp.id),
        "full_name": emp.full_name,
        "email": emp.email,
        "department": emp.department,
        "position": emp.position,
        "status": emp.status,
        "computers_count": 0,
        "created_at": emp.created_at,
        "updated_at": emp.updated_at,
    }


@router.get("/{employee_id}", response_model=EmployeeDetailResponse)
async def get_employee(employee_id: str, db: AsyncSession = Depends(get_db)):
    try:
        emp_uuid = uuid.UUID(employee_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат UUID сотрудника")

    result = await db.execute(select(Employee).where(Employee.id == emp_uuid))
    emp = result.scalar_one_or_none()
    if not emp:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")

    comps_out = []
    for c in emp.computers:
        comps_out.append({
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
            "employee_id": str(emp.id),
            "installed_count": len(c.installed_software) if c.installed_software else 0,
            "created_at": c.created_at,
            "updated_at": c.updated_at,
        })

    return {
        "id": str(emp.id),
        "full_name": emp.full_name,
        "email": emp.email,
        "department": emp.department,
        "position": emp.position,
        "status": emp.status,
        "computers_count": len(emp.computers) if emp.computers else 0,
        "computers": comps_out,
        "created_at": emp.created_at,
        "updated_at": emp.updated_at,
    }


@router.put("/{employee_id}", response_model=EmployeeResponse)
async def update_employee(
    employee_id: str, payload: EmployeeUpdate, db: AsyncSession = Depends(get_db)
):
    try:
        emp_uuid = uuid.UUID(employee_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат UUID")

    result = await db.execute(select(Employee).where(Employee.id == emp_uuid))
    emp = result.scalar_one_or_none()
    if not emp:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(emp, field, value)

    await db.commit()
    await db.refresh(emp)

    return {
        "id": str(emp.id),
        "full_name": emp.full_name,
        "email": emp.email,
        "department": emp.department,
        "position": emp.position,
        "status": emp.status,
        "computers_count": len(emp.computers) if emp.computers else 0,
        "created_at": emp.created_at,
        "updated_at": emp.updated_at,
    }


@router.delete("/{employee_id}")
async def delete_employee(employee_id: str, db: AsyncSession = Depends(get_db)):
    try:
        emp_uuid = uuid.UUID(employee_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат UUID")

    result = await db.execute(select(Employee).where(Employee.id == emp_uuid))
    emp = result.scalar_one_or_none()
    if not emp:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")

    await db.delete(emp)
    await db.commit()
    return {"success": True}
