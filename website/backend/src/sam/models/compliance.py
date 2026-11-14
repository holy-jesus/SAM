import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Numeric, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from sam.db import Base

if TYPE_CHECKING:
    from sam.models.computer import Computer
    from sam.models.catalog import SoftwareCatalog


class ComplianceAlert(Base):
    __tablename__ = "compliance_alerts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    alert_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # license_overuse, zombie_software, prohibited_software, shadow_it, commercial_risk
    severity: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True
    )  # 'info', 'warning', 'critical'

    computer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("computers.id", ondelete="CASCADE"), nullable=True, index=True
    )
    software_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("software_catalog.id", ondelete="CASCADE"), nullable=True, index=True
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    financial_risk_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(50), default="active", nullable=False, index=True
    )  # 'active', 'acknowledged', 'resolved'

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    computer: Mapped[Optional["Computer"]] = relationship("Computer", lazy="joined")
    software: Mapped[Optional["SoftwareCatalog"]] = relationship("SoftwareCatalog", lazy="joined")
