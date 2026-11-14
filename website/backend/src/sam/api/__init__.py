from fastapi import APIRouter
from sam.api.auth import router as auth_router
from sam.api.dashboard import router as dashboard_router
from sam.api.compliance import router as compliance_router
from sam.api.employees import router as employees_router
from sam.api.computers import router as computers_router
from sam.api.catalog import router as catalog_router
from sam.api.licenses import router as licenses_router
from sam.api.categories import router as categories_router
from sam.api.classifiers import router as classifiers_router
from sam.api.registry import router as registry_router
from sam.api.installed_software import router as installed_software_router
from sam.api.connector import router as connector_router
from sam.api.ai import router as ai_router
from sam.api.matcher import router as matcher_router

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(dashboard_router)
api_router.include_router(compliance_router)
api_router.include_router(employees_router)
api_router.include_router(computers_router)
api_router.include_router(catalog_router)
api_router.include_router(licenses_router)
api_router.include_router(categories_router)
api_router.include_router(classifiers_router)
api_router.include_router(registry_router)
api_router.include_router(installed_software_router)
api_router.include_router(connector_router)
api_router.include_router(ai_router)
api_router.include_router(matcher_router)
