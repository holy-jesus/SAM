from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Dict, Any, Optional
from sqlalchemy import select, func, and_, or_, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sam.config import settings
from sam.models.catalog import SoftwareCatalog
from sam.models.license import License
from sam.models.installed_software import InstalledSoftware
from sam.models.computer import Computer
from sam.models.employee import Employee
from sam.models.category import SoftwareCategory
from sam.models.compliance import ComplianceAlert


async def recalculate_compliance_alerts(db: AsyncSession) -> int:
    """
    Clears existing active alerts and recalculates all compliance rules:
    - License deficit / overuse
    - Zombie software (unused > 60 days or assigned to dismissed employees)
    - Prohibited / dangerous software
    - Shadow IT
    """
    # 1. Remove current active alerts to refresh
    await db.execute(delete(ComplianceAlert).where(ComplianceAlert.status == "active"))
    
    new_alerts: List[ComplianceAlert] = []
    now = datetime.now(timezone.utc)
    zombie_threshold = now - timedelta(days=settings.ZOMBIE_THRESHOLD_DAYS)

    # 2. Rule 1: License balance & Overuse
    catalogs_result = await db.execute(select(SoftwareCatalog))
    catalogs = catalogs_result.scalars().all()

    for cat in catalogs:
        # Sum purchased
        lic_result = await db.execute(
            select(func.sum(License.total_purchased), func.max(License.unit_cost))
            .where(License.software_id == cat.id)
        )
        purchased_sum, max_unit_cost = lic_result.one()
        purchased_count = int(purchased_sum or 0)
        unit_cost = Decimal(str(max_unit_cost or "0.00"))

        # Count active installations
        inst_count_res = await db.execute(
            select(func.count(InstalledSoftware.id))
            .where(
                and_(
                    InstalledSoftware.catalog_software_id == cat.id,
                    InstalledSoftware.is_deleted == False
                )
            )
        )
        installed_count = inst_count_res.scalar_one()

        if cat.license_type in ["Commercial", "Платный"] and installed_count > purchased_count:
            excess = installed_count - purchased_count
            risk_amt = unit_cost * Decimal(excess)
            new_alerts.append(
                ComplianceAlert(
                    alert_type="license_overuse",
                    severity="critical",
                    software_id=cat.id,
                    title=f"Дефицит лицензий: {cat.name}",
                    description=(
                        f"Установлено {installed_count} шт. при закупленных {purchased_count} "
                        f"(дефицит {excess} шт.). Штрафной финансовый риск при аудите: {risk_amt:,.2f} руб."
                    ),
                    financial_risk_amount=risk_amt,
                    status="active",
                )
            )

    # 3. Rule 2: Prohibited Software
    prohibited_res = await db.execute(
        select(InstalledSoftware)
        .join(SoftwareCategory, InstalledSoftware.category_id == SoftwareCategory.id)
        .where(
            and_(
                InstalledSoftware.is_deleted == False,
                or_(
                    SoftwareCategory.is_problematic == True,
                    SoftwareCategory.risk_level == "critical"
                )
            )
        )
    )
    prohibited_installs = prohibited_res.scalars().all()

    for inst in prohibited_installs:
        comp = inst.computer
        emp_name = comp.employee.full_name if comp and comp.employee else "Не привязан"
        host = comp.hostname if comp else "Unknown Host"
        new_alerts.append(
            ComplianceAlert(
                alert_type="prohibited_software",
                severity="critical",
                computer_id=comp.id if comp else None,
                software_id=inst.catalog_software_id,
                title=f"Запрещённое ПО: {inst.raw_display_name} на {host}",
                description=(
                    f"На рабочей станции {host} (сотрудник: {emp_name}) обнаружено ПО "
                    f"из категории «Запрещенный к использованию» ({inst.raw_display_name}). Угроза ИБ!"
                ),
                financial_risk_amount=Decimal("150000.00"),
                status="active",
            )
        )

    # 4. Rule 3: Zombie Software (Dismissed employees or inactive > N days)
    # 4a: Computer belongs to a dismissed employee
    dismissed_res = await db.execute(
        select(InstalledSoftware)
        .join(Computer, InstalledSoftware.computer_id == Computer.id)
        .join(Employee, Computer.employee_id == Employee.id)
        .where(
            and_(
                InstalledSoftware.is_deleted == False,
                Employee.status == "dismissed"
            )
        )
    )
    dismissed_installs = dismissed_res.scalars().all()

    for inst in dismissed_installs:
        comp = inst.computer
        emp = comp.employee if comp else None
        host = comp.hostname if comp else "Unknown"
        emp_name = emp.full_name if emp else "Уволенный сотрудник"

        # Calculate unit cost
        cost = Decimal("25000.00")
        if inst.catalog_software and inst.catalog_software.licenses:
            cost = max(Decimal(l.unit_cost) for l in inst.catalog_software.licenses)

        new_alerts.append(
            ComplianceAlert(
                alert_type="zombie_software",
                severity="warning",
                computer_id=comp.id if comp else None,
                software_id=inst.catalog_software_id,
                title=f"ПО уволенного сотрудника: {inst.raw_display_name} ({host})",
                description=(
                    f"Сотрудник {emp_name} уволен, однако рабочая станция {host} всё ещё числится "
                    f"с установленным ПО '{inst.raw_display_name}'. Лицензия простаивает."
                ),
                financial_risk_amount=cost,
                status="active",
            )
        )

    # 4b: Software not launched for > threshold days
    inactive_res = await db.execute(
        select(InstalledSoftware)
        .where(
            and_(
                InstalledSoftware.is_deleted == False,
                InstalledSoftware.last_launched_at.is_not(None),
                InstalledSoftware.last_launched_at < zombie_threshold
            )
        )
    )
    inactive_installs = inactive_res.scalars().all()

    for inst in inactive_installs:
        comp = inst.computer
        host = comp.hostname if comp else "Unknown"
        cost = Decimal("15000.00")
        if inst.catalog_software and inst.catalog_software.licenses:
            cost = max(Decimal(l.unit_cost) for l in inst.catalog_software.licenses)

        days_inactive = (now - inst.last_launched_at).days if inst.last_launched_at else 60
        new_alerts.append(
            ComplianceAlert(
                alert_type="zombie_software",
                severity="warning",
                computer_id=comp.id if comp else None,
                software_id=inst.catalog_software_id,
                title=f"Зомби-софт: {inst.raw_display_name} не запускался {days_inactive} дн.",
                description=(
                    f"На хосте {host} софт '{inst.raw_display_name}' не использовался {days_inactive} дней. "
                    f"Рекомендуется высвободить лицензию в корпоративный пул."
                ),
                financial_risk_amount=cost,
                status="active",
            )
        )

    # Save alerts
    for a in new_alerts:
        db.add(a)

    await db.commit()
    return len(new_alerts)


async def get_compliance_balance_list(db: AsyncSession) -> List[Dict[str, Any]]:
    catalogs_result = await db.execute(select(SoftwareCatalog))
    catalogs = catalogs_result.scalars().all()

    balance_list: List[Dict[str, Any]] = []

    for cat in catalogs:
        # Sum purchased
        lic_result = await db.execute(
            select(func.sum(License.total_purchased), func.max(License.unit_cost))
            .where(License.software_id == cat.id)
        )
        purchased_sum, max_unit_cost = lic_result.one()
        purchased_count = int(purchased_sum or 0)
        unit_cost = float(max_unit_cost or 0.0)

        # Count installed
        inst_count_res = await db.execute(
            select(func.count(InstalledSoftware.id))
            .where(
                and_(
                    InstalledSoftware.catalog_software_id == cat.id,
                    InstalledSoftware.is_deleted == False
                )
            )
        )
        installed_count = inst_count_res.scalar_one()
        balance = purchased_count - installed_count

        is_prohibited = (
            cat.category is not None and (cat.category.is_problematic or cat.category.risk_level == "critical")
        )

        penalty = 0.0
        if is_prohibited:
            status = "critical_overuse"
            penalty = installed_count * 100000.0
        elif cat.license_type in ["Commercial", "Платный"]:
            if balance < 0:
                status = "critical_overuse"
                penalty = abs(balance) * unit_cost
            elif balance > 0 and installed_count == 0:
                status = "underutilized"
            else:
                status = "normal"
        else:
            status = "normal"

        balance_list.append({
            "software_id": str(cat.id),
            "software_name": cat.name,
            "vendor": cat.vendor,
            "license_type": cat.license_type,
            "purchased_count": purchased_count,
            "installed_count": installed_count,
            "balance": balance,
            "unit_cost": unit_cost,
            "total_penalty_risk_rub": penalty,
            "status": status,
            "is_prohibited": is_prohibited,
        })

    return balance_list
