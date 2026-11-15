from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from sam.schemas.classifier import ClassifierResponse
from sam.schemas.registry import RuSoftwareRegistryResponse
from sam.schemas.category import CategoryResponse


class CatalogItemBase(BaseModel):
    name: str
    vendor: Optional[str] = None
    description: Optional[str] = None
    classifier_id: Optional[int] = None
    ru_registry_id: Optional[int] = None
    category_id: Optional[int] = None
    license_type: str = "Commercial"
    max_installations: int = 0
    responsible_person: str = "Администратор SAM"
    approval_status: str = "approved"


class CatalogItemCreate(CatalogItemBase):
    pass


class CatalogItemUpdate(BaseModel):
    name: Optional[str] = None
    vendor: Optional[str] = None
    description: Optional[str] = None
    classifier_id: Optional[int] = None
    ru_registry_id: Optional[int] = None
    category_id: Optional[int] = None
    license_type: Optional[str] = None
    max_installations: Optional[int] = None
    responsible_person: Optional[str] = None
    approval_status: Optional[str] = None


class CatalogItemResponse(CatalogItemBase):
    id: str
    active_installations_count: int = 0
    has_substitution: Optional[bool] = None
    substitutions_count: int = 0
    is_domestic: bool = False
    substitution_status: Optional[str] = None
    classifier: Optional[ClassifierResponse] = None
    ru_registry: Optional[RuSoftwareRegistryResponse] = None
    category: Optional[CategoryResponse] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
