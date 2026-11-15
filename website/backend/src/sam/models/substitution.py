import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Integer, DateTime, ForeignKey, Text, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from sam.db import Base

if TYPE_CHECKING:
    from sam.models.catalog import SoftwareCatalog
    from sam.models.registry import RuSoftwareRegistry


class ImportSubstitution(Base):
    """
    Таблица сопоставления иностранного ПО и его отечественных аналогов
    на основе сервиса импортозамещения reestr.digital.gov.ru и каталога АРПП.
    """
    __tablename__ = "import_substitutions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    foreign_software_name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    russian_software_name: Mapped[str] = mapped_column(String(500), index=True, nullable=False)
    russian_reg_number: Mapped[Optional[str]] = mapped_column(String(50), index=True, nullable=True)
    source: Mapped[str] = mapped_column(String(50), default="registry", nullable=False)  # 'registry' | 'arppsoft'
    owner_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    class_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    class_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    registration_date: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    registry_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    ru_registry_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("ru_software_registry.id", ondelete="SET NULL"), nullable=True
    )
    catalog_software_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("software_catalog.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    ru_registry: Mapped[Optional["RuSoftwareRegistry"]] = relationship("RuSoftwareRegistry", lazy="joined")
    catalog_software: Mapped[Optional["SoftwareCatalog"]] = relationship(
        "SoftwareCatalog", back_populates="substitutions", lazy="joined"
    )


class SubstitutionCache(Base):
    """
    Таблица кэширования результатов проверки сервиса импортозамещения reestr.digital.gov.ru.
    Хранит факт наличия отечественных аналогов, их количество, дату проверки и срок действия (TTL),
    предотвращая избыточные сетевые запросы и исключая DDoS внешнего сервиса.
    """
    __tablename__ = "substitution_cache"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    software_name: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    has_substitution: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    substitutions_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_domestic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="checked", nullable=False)  # 'checked', 'domestic', 'not_found', 'error'

    catalog_software_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("software_catalog.id", ondelete="SET NULL"), nullable=True, index=True
    )
    last_checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    catalog_software: Mapped[Optional["SoftwareCatalog"]] = relationship("SoftwareCatalog", lazy="joined")

