from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sam.config import settings
from sam.db import init_db, AsyncSessionLocal
from sam.api import api_router
from sam.init_data import seed_database_if_empty


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Startup: Initialize tables and extension
    try:
        await init_db()
        print("[+] База данных успешно инициализирована.")
    except Exception as e:
        print(f"[!] Ошибка инициализации БД: {e}")

    # 2. Seed initial data if database is fresh
    if settings.AUTO_SEED:
        try:
            async with AsyncSessionLocal() as session:
                await seed_database_if_empty(session)
                print("[+] Первоначальные данные (каталог, классификаторы, категории) успешно загружены.")
        except Exception as e:
            print(f"[!] Ошибка загрузки начальных данных: {e}")

    yield

    # Shutdown logic if needed
    print("[*] Остановка сервиса SAM Backend...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Интеллектуальная система учёта и комплаенса программного обеспечения (Software Asset Management)",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes with prefix /api/v1
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/")
async def root():
    return {
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
