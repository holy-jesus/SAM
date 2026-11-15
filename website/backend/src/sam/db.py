from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import UserDefinedType
from sqlalchemy import text
from sam.config import settings

# Support Vector type even if pgvector package is not installed locally
try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    class Vector(UserDefinedType):
        def __init__(self, dim: int = 384):
            self.dim = dim

        def get_col_spec(self, **kw):
            return f"vector({self.dim})"

        def bind_processor(self, dialect):
            def process(value):
                if value is None:
                    return None
                if isinstance(value, (list, tuple)):
                    return "[" + ",".join(str(float(x)) for x in value) + "]"
                return str(value)
            return process

        def result_processor(self, dialect, coltype):
            def process(value):
                if value is None:
                    return None
                if isinstance(value, str):
                    clean = value.strip("[]() ")
                    if not clean:
                        return []
                    return [float(x) for x in clean.split(",") if x.strip()]
                return value
            return process


class Base(AsyncAttrs, DeclarativeBase):
    pass


engine = create_async_engine(
    settings.async_database_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    async with engine.begin() as conn:
        # Enable pgvector extension if supported on PostgreSQL
        if "postgresql" in settings.async_database_url:
            try:
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            except Exception as e:
                print(f"Notice: pgvector extension creation skipped or already present: {e}")
        # NOTE: Table schema is managed by Alembic migrations (alembic upgrade head).
        # Do NOT call Base.metadata.create_all here — it bypasses migrations
        # and would leave existing columns with wrong types unchanged.
