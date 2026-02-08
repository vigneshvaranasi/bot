from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from src.api.core.config import DATABASE_URL
from src.api.db.base import Base  # noqa: F401 - re-exported for convenience

engine = create_async_engine(DATABASE_URL)

async_session = sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)


async def get_session():
    """Async session generator for FastAPI dependency injection.

    Yields:
        AsyncSession: Database session that auto-commits on success and rolls back on error.
    """
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise