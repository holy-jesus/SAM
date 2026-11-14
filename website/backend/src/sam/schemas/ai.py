from typing import Optional, List, Any
from datetime import datetime
from pydantic import BaseModel


class SmartMatchRequest(BaseModel):
    raw_process_name: str


class SmartMatchResponse(BaseModel):
    raw_process_name: str
    matched_catalog_software_id: Optional[str] = None
    matched_name: Optional[str] = None
    vendor: Optional[str] = None
    confidence: float
    reasoning: str


class BatchNormalizeResponse(BaseModel):
    normalized_count: int
    matched_count: int


class EulaAnalyzeRequest(BaseModel):
    eula_text: str
    license_id: Optional[str] = None


class EulaAnalysisResponse(BaseModel):
    commercial_use_allowed: bool
    risk_level: str
    has_auto_renewal: bool
    trial_period_days: Optional[int] = None
    key_restrictions: List[str]
    summary_ru: str
    analyzed_at: Optional[datetime] = None


class AIChatRequest(BaseModel):
    query: str


class AIChatResponse(BaseModel):
    answer: str
    sql_executed: Optional[str] = None
    data: Optional[List[Any]] = None
