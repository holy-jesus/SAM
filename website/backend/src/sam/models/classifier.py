from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sam.db import Base


class SoftwareClassifier(Base):
    __tablename__ = "software_classifiers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    section_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    section_name: Mapped[str] = mapped_column(String(255), nullable=False)
    class_name: Mapped[str] = mapped_column(Text, nullable=False)
