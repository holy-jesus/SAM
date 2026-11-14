import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, Any, TYPE_CHECKING
from sqlalchemy import String, Integer, Numeric, Date, DateTime, ForeignKey, Text, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from sam.db import Base

if TYPE_CHECKING:
    from sam.models.catalog import SoftwareCatalog


class License(Base):
    __tablename__ = "licenses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    software_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("software_catalog.id", ondelete="CASCADE"), nullable=False, index=True
    )
    license_name: Mapped[str] = mapped_column(String(255), nullable=False)
    license_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'Платный', 'Бесплатный', etc.
    license_model: Mapped[str] = mapped_column(String(50), default="per_device", nullable=False)
    total_purchased: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="RUB", nullable=False)
    valid_from: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    valid_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    eula_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    eula_analysis: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    software: Mapped["SoftwareCatalog"] = relationship("SoftwareCatalog", back_populates="licenses", lazy="joined")
