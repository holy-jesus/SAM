import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Boolean, Float, DateTime, ForeignKey, Text, func, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from sam.db import Base

if TYPE_CHECKING:
    from sam.models.computer import Computer
    from sam.models.catalog import SoftwareCatalog
    from sam.models.category import SoftwareCategory


class InstalledSoftware(Base):
    __tablename__ = "installed_software"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    computer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("computers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    raw_display_name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    raw_publisher: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    raw_version: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    install_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    binary_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    last_launched_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(50), default="automatic", nullable=False)  # 'agent', 'automatic', 'manual'

    catalog_software_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("software_catalog.id", ondelete="SET NULL"), nullable=True, index=True
    )
    category_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("software_categories.id", ondelete="SET NULL"), nullable=True, index=True
    )
    match_confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    is_verified_by_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    computer: Mapped["Computer"] = relationship("Computer", back_populates="installed_software", lazy="joined")
    catalog_software: Mapped[Optional["SoftwareCatalog"]] = relationship(
        "SoftwareCatalog", back_populates="installations", lazy="joined"
    )
    category: Mapped[Optional["SoftwareCategory"]] = relationship("SoftwareCategory", lazy="joined")
