from sam.schemas.auth import (
    SetupStatusResponse,
    InitAdminRequest,
    LoginRequest,
    TokenResponse,
    UserResponse,
)
from sam.schemas.category import (
    CategoryBase,
    CategoryCreate,
    CategoryUpdate,
    CategoryResponse,
)
from sam.schemas.classifier import ClassifierResponse
from sam.schemas.registry import (
    RuSoftwareRegistryResponse,
    RegistryStatusResponse,
    RegistrySyncResponse,
)
from sam.schemas.license import (
    LicenseBase,
    LicenseCreate,
    LicenseUpdate,
    LicenseResponse,
)
from sam.schemas.catalog import (
    CatalogItemBase,
    CatalogItemCreate,
    CatalogItemUpdate,
    CatalogItemResponse,
)
from sam.schemas.installed_software import (
    InstalledSoftwareResponse,
    InstalledSoftwareManualCreate,
    UpdateSoftwareCategoryRequest,
)
from sam.schemas.computer import (
    ComputerBase,
    ComputerCreate,
    ComputerUpdate,
    ComputerResponse,
)
from sam.schemas.employee import (
    EmployeeBase,
    EmployeeCreate,
    EmployeeUpdate,
    EmployeeResponse,
    EmployeeDetailResponse,
)
from sam.schemas.compliance import (
    ComplianceBalanceItem,
    ComplianceAlertResponse,
    RecalculateResponse,
)
from sam.schemas.dashboard import DashboardSummary
from sam.schemas.connector import (
    AgentReportRequest,
    AgentHeartbeatRequest,
    ImportResultResponse,
    ImportHistoryResponse,
)
from sam.schemas.ai import (
    SmartMatchRequest,
    SmartMatchResponse,
    BatchNormalizeResponse,
    EulaAnalyzeRequest,
    EulaAnalysisResponse,
    AIChatRequest,
    AIChatResponse,
)
