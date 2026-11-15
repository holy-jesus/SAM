from typing import Optional
from sqlalchemy import String, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column
from sam.db import Base


class EmployeeCategory(Base):
    __tablename__ = "employee_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    allowed_software_list: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
