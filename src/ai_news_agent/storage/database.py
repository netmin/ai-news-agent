"""Database connection and session management."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from loguru import logger
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from ..config import settings
from .models import Base


class DatabaseManager:
    """Manages database connections and sessions."""

    def __init__(self, database_url: str | None = None):
        """Initialize database manager.

        Args:
            database_url: Database URL. If None, uses settings.database_url
        """
        self.database_url = database_url or settings.database_url
        self._engine: AsyncEngine | None = None
        self._sessionmaker: async_sessionmaker | None = None

    @property
    def engine(self) -> AsyncEngine:
        """Get or create the async engine."""
        if self._engine is None:
            # SQLite doesn't support pool settings
            if self.database_url.startswith("sqlite"):
                self._engine = create_async_engine(
                    self.database_url,
                    echo=settings.database_echo if hasattr(settings, "database_echo") else False,
                )
            else:
                self._engine = create_async_engine(
                    self.database_url,
                    echo=settings.database_echo if hasattr(settings, "database_echo") else False,
                    pool_pre_ping=True,
                    pool_size=5,
                    max_overflow=10,
                )
            logger.info(f"Created database engine for {self.database_url}")
        return self._engine

    @property
    def sessionmaker(self) -> async_sessionmaker:
        """Get or create the async session maker."""
        if self._sessionmaker is None:
            self._sessionmaker = async_sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
        return self._sessionmaker

    async def init_db(self) -> None:
        """Initialize database tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables initialized")

    async def drop_all(self) -> None:
        """Drop all database tables. Use with caution!"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            logger.warning("All database tables dropped")

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get an async database session.

        Yields:
            AsyncSession: Database session

        Example:
            async with db_manager.get_session() as session:
                # Use session here
                result = await session.execute(select(NewsItemDB))
        """
        async with self.sessionmaker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def close(self) -> None:
        """Close database connections."""
        if self._engine:
            await self._engine.dispose()
            logger.info("Database connections closed")

    async def health_check(self) -> bool:
        """Check if database is accessible.

        Returns:
            bool: True if database is healthy
        """
        try:
            from sqlalchemy import text
            async with self.get_session() as session:
                await session.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False


# Global database manager instance
_db_manager: DatabaseManager | None = None


def get_db_manager() -> DatabaseManager:
    """Get the global database manager instance.

    Returns:
        DatabaseManager: Global database manager
    """
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


async def init_database() -> None:
    """Initialize the database with all tables."""
    db_manager = get_db_manager()
    await db_manager.init_db()


async def close_database() -> None:
    """Close database connections."""
    db_manager = get_db_manager()
    await db_manager.close()
