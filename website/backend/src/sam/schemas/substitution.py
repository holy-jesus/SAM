from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class SubstitutionItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    foreign_software_name: str
    russian_software_name: str
    russian_reg_number: Optional[str] = None
    source: str
    owner_name: Optional[str] = None
    class_code: Optional[str] = None
    class_name: Optional[str] = None
    registration_date: Optional[str] = None
    registry_url: Optional[str] = None
    ru_registry_id: Optional[int] = None
    catalog_software_id: Optional[str] = None
    created_at: Optional[datetime] = None


class SubstitutionSearchResponse(BaseModel):
    query: str
    total_found: int
    items: List[SubstitutionItemResponse]


class SubstitutionSyncResponse(BaseModel):
    success: bool
    imported_count: int
    message: str


class SubstitutionStatusResponse(BaseModel):
    software_name: str
    status: str
    has_substitution: bool = False
    substitutions_count: int = 0
    is_domestic: bool = False
    last_checked_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    message: Optional[str] = None


class SubstitutionCacheItemResponse(BaseModel):
    id: str
    software_name: str
    has_substitution: bool
    substitutions_count: int
    is_domestic: bool
    status: str
    catalog_software_id: Optional[str] = None
    last_checked_at: datetime
    expires_at: datetime
    error_message: Optional[str] = None
