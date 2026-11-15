from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class InstalledSoftwareResponse(BaseModel):
    id: str
    computer_id: str
    computer_hostname: Optional[str] = None
    computer_serial: Optional[str] = None
    raw_display_name: str
    raw_publisher: Optional[str] = None
    raw_version: Optional[str] = None
    install_path: Optional[str] = None
    binary_hash: Optional[str] = None
    last_launched_at: Optional[datetime] = None
    source: str = "automatic"
    catalog_software_id: Optional[str] = None
    catalog_software_name: Optional[str] = None
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    is_problematic: bool = False
    match_confidence: float = 0.0
    is_verified_by_admin: bool = False
    is_deleted: bool = False
    has_substitution: Optional[bool] = None
    substitutions_count: int = 0
    is_domestic: bool = False
    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class InstalledSoftwareManualCreate(BaseModel):
    catalog_software_id: Optional[str] = None
    raw_display_name: Optional[str] = None
    raw_publisher: Optional[str] = None
    raw_version: Optional[str] = "1.0"
    install_path: Optional[str] = None
    last_launched_at: Optional[datetime] = None


class UpdateSoftwareCategoryRequest(BaseModel):
    category_id: int
