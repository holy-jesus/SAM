from typing import Optional, List, Any
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class AgentSoftwareItem(BaseModel):
    display_name: str
    publisher: Optional[str] = None
    version: Optional[str] = None
    install_path: Optional[str] = None
    binary_hash: Optional[str] = None
    last_launched_at: Optional[datetime] = None
    is_running: bool = False


class AgentReportRequest(BaseModel):
    serial_number: str
    hostname: str
    ip_address: Optional[str] = None
    mac_address: Optional[str] = None
    os_name: Optional[str] = None
    os_version: Optional[str] = None
    cpu: Optional[str] = None
    ram_mb: Optional[int] = None
    installed_software: List[AgentSoftwareItem] = []


class AgentHeartbeatRequest(BaseModel):
    serial_number: str
    hostname: Optional[str] = None


class ImportResultResponse(BaseModel):
    filename: str
    total_rows: int
    computers_affected: int
    software_rows_imported: int
    matched_automatically: int


class ImportHistoryResponse(BaseModel):
    id: str
    filename: str
    total_rows: int
    computers_affected: int
    software_rows_imported: int
    matched_automatically: int
    status: str
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
