from datetime import datetime, date
from typing import Optional, List
from sqlalchemy import String, Boolean, Text, Date, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from sam.db import Base, Vector


class RuSoftwareRegistry(Base):
    __tablename__ = "ru_software_registry"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    reg_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    alternative_names: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    software_class: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    vendor_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    vendor_inn: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    documentation_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_ai: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    excluded_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    embedding: Mapped[Optional[List[float]]] = mapped_column(Vector(384), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
