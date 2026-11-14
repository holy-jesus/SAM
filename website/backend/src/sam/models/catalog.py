import uuid
from datetime import datetime
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import String, Integer, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from sam.db import Base, Vector

if TYPE_CHECKING:
    from sam.models.classifier import SoftwareClassifier
    from sam.models.registry import RuSoftwareRegistry
    from sam.models.category import SoftwareCategory
    from sam.models.license import License
    from sam.models.installed_software import InstalledSoftware


class SoftwareCatalog(Base):
    __tablename__ = "software_catalog"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    vendor: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    classifier_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("software_classifiers.id"), nullable=True
    )
    ru_registry_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("ru_software_registry.id", ondelete="SET NULL"), nullable=True
    )
    category_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("software_categories.id"), nullable=True
    )

    license_type: Mapped[str] = mapped_column(String(50), default="Commercial", nullable=False)
    max_installations: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # 0 = unlimited
    responsible_person: Mapped[str] = mapped_column(String(255), default="Администратор SAM", nullable=False)
    approval_status: Mapped[str] = mapped_column(String(50), default="approved", nullable=False)
    embedding: Mapped[Optional[List[float]]] = mapped_column(Vector(1536), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    classifier: Mapped[Optional["SoftwareClassifier"]] = relationship("SoftwareClassifier", lazy="joined")
    ru_registry: Mapped[Optional["RuSoftwareRegistry"]] = relationship("RuSoftwareRegistry", lazy="joined")
    category: Mapped[Optional["SoftwareCategory"]] = relationship("SoftwareCategory", lazy="joined")
    licenses: Mapped[List["License"]] = relationship(
        "License", back_populates="software", cascade="all, delete-orphan", lazy="selectin"
    )
    installations: Mapped[List["InstalledSoftware"]] = relationship(
        "InstalledSoftware", back_populates="catalog_software", lazy="selectin"
    )
