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

            try:
                # Гарантируем, что тип колонок embedding приведен к vector(1536) вместо double precision[]
                await conn.execute(text("""
                    DO $$
                    BEGIN
                        IF EXISTS (
                            SELECT 1 FROM information_schema.columns 
                            WHERE table_name = 'ru_software_registry' AND column_name = 'embedding' AND data_type = 'ARRAY'
                        ) THEN
                            ALTER TABLE ru_software_registry 
                            ALTER COLUMN embedding TYPE vector(1536) 
                            USING CASE 
                                WHEN embedding IS NULL THEN NULL 
                                ELSE (replace(replace(embedding::text, '{', '['), '}', ']')::vector) 
                            END;
                        END IF;

                        IF EXISTS (
                            SELECT 1 FROM information_schema.columns 
                            WHERE table_name = 'software_catalog' AND column_name = 'embedding' AND data_type = 'ARRAY'
                        ) THEN
                            ALTER TABLE software_catalog 
                            ALTER COLUMN embedding TYPE vector(1536) 
                            USING CASE 
                                WHEN embedding IS NULL THEN NULL 
                                ELSE (replace(replace(embedding::text, '{', '['), '}', ']')::vector) 
                            END;
                        END IF;

                        IF EXISTS (
                            SELECT 1 FROM information_schema.columns 
                            WHERE table_name = 'process_signatures' AND column_name = 'embedding' AND data_type = 'ARRAY'
                        ) THEN
                            ALTER TABLE process_signatures 
                            ALTER COLUMN embedding TYPE vector(1536) 
                            USING CASE 
                                WHEN embedding IS NULL THEN NULL 
                                ELSE (replace(replace(embedding::text, '{', '['), '}', ']')::vector) 
                            END;
                        END IF;

                        -- Расширение строковых колонок ru_software_registry для списков ИНН и совладельцев
                        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'ru_software_registry') THEN
                            ALTER TABLE ru_software_registry ALTER COLUMN vendor_inn TYPE TEXT;
                            ALTER TABLE ru_software_registry ALTER COLUMN vendor_name TYPE TEXT;
                            ALTER TABLE ru_software_registry ALTER COLUMN name TYPE TEXT;
                            ALTER TABLE ru_software_registry ALTER COLUMN reg_number TYPE VARCHAR(100);
                        END IF;

                        -- Расширение колонок software_classifiers
                        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'software_classifiers') THEN
                            ALTER TABLE software_classifiers ALTER COLUMN class_name TYPE TEXT;
                            ALTER TABLE software_classifiers ALTER COLUMN section_name TYPE TEXT;
                        END IF;
                    END $$;
                """))
            except Exception as e:
                print(f"Notice: embedding column conversion skipped or failed: {e}")
        # NOTE: Table schema is managed by Alembic migrations (alembic upgrade head).
        # Do NOT call Base.metadata.create_all here — it bypasses migrations
        # and would leave existing columns with wrong types unchanged.
