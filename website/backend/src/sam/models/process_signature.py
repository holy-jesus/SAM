import uuid
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from sam.db import Base, Vector

if TYPE_CHECKING:
    from sam.models.catalog import SoftwareCatalog
    from sam.models.registry import RuSoftwareRegistry


class ProcessSignature(Base):
    """
    Таблица для самообучающейся базы сигнатур и сопоставлений процессов:
    Сохраняет результаты обнаружения по хэшу, Единому реестру РФ, Wikimedia,
    векторным эмбеддингам и нейросети (OpenAI LLM), накапливая базу знаний.
    """
    __tablename__ = "process_signatures"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    process_name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    normalized_name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    binary_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    
    catalog_software_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("software_catalog.id", ondelete="CASCADE"), nullable=True, index=True
    )
    ru_registry_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("ru_software_registry.id", ondelete="SET NULL"), nullable=True
    )

    vendor: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    match_source: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # 'hash', 'ru_registry', 'embedding', 'wikimedia', 'openai', 'admin'
    embedding: Mapped[Optional[List[float]]] = mapped_column(Vector(1536), nullable=True)
    times_matched: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    catalog_software: Mapped[Optional["SoftwareCatalog"]] = relationship("SoftwareCatalog", lazy="joined")
    ru_registry: Mapped[Optional["RuSoftwareRegistry"]] = relationship("RuSoftwareRegistry", lazy="joined")
