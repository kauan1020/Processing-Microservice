from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from contextlib import asynccontextmanager
from typing import AsyncGenerator
import logging

logger = logging.getLogger(__name__)


class DatabaseConnection:
    """
    Database connection manager for PostgreSQL with async SQLAlchemy.

    This class manages the database connection lifecycle, session management,
    and provides connection pooling for optimal performance and resource usage.

    It implements the async context manager pattern for proper connection
    handling and ensures database sessions are properly closed after use.
    """

    def __init__(self, database_url: str, echo: bool = False):
        """
        Initialize database connection with the provided configuration.

        Args:
            database_url: PostgreSQL connection string
            echo: Whether to log SQL queries for debugging
        """
        self.database_url = database_url
        self.echo = echo
        self._engine = None
        self._session_factory = None

    def initialize(self) -> None:
        """
        Initialize the database engine and session factory.

        Creates the async engine with optimized connection pool settings
        and configures the session factory for dependency injection.
        """
        try:
            logger.info(f"Inicializando database com URL: {self.database_url}")

            self._engine = create_async_engine(
                self.database_url,
                echo=self.echo,
                pool_size=10,
                max_overflow=20,
                pool_timeout=30,
                pool_recycle=3600,
                pool_pre_ping=True,  # Adicionar para verificar conexões
                poolclass=NullPool if "sqlite" in self.database_url else None
            )

            self._session_factory = async_sessionmaker(
                bind=self._engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=True,
                autocommit=False
            )

            logger.info("✅ Database connection initialized successfully")
        except Exception as e:
            logger.error(f"❌ Erro ao inicializar database: {str(e)}")
            raise

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Async context manager for database sessions.

        Provides a database session with automatic transaction management,
        ensuring proper cleanup and error handling.

        Yields:
            AsyncSession: Database session for executing queries

        Raises:
            Exception: Re-raises any database-related exceptions after rollback
        """
        if not self._session_factory:
            logger.error("❌ Database not initialized. Call initialize() first.")
            raise RuntimeError("Database not initialized. Call initialize() first.")

        session = None
        try:
            logger.debug("🔄 Criando nova sessão de banco")
            session = self._session_factory()

            # Testar a conexão antes de usar
            from sqlalchemy import text
            await session.execute(text("SELECT 1"))

            logger.debug("✅ Sessão de banco criada com sucesso")
            yield session
            await session.commit()
            logger.debug("✅ Commit realizado com sucesso")

        except Exception as e:
            logger.error(f"❌ Database session error: {str(e)}")
            logger.error(f"❌ Error type: {type(e).__name__}")
            logger.error(f"❌ Database URL: {self.database_url}")

            if session:
                try:
                    await session.rollback()
                    logger.debug("🔄 Rollback realizado")
                except Exception as rollback_error:
                    logger.error(f"❌ Erro no rollback: {str(rollback_error)}")

            raise
        finally:
            if session:
                try:
                    await session.close()
                    logger.debug("🔄 Sessão fechada")
                except Exception as close_error:
                    logger.error(f"❌ Erro ao fechar sessão: {str(close_error)}")

    async def health_check(self) -> bool:
        """
        Perform a health check on the database connection.

        Tests the database connectivity by executing a simple query
        and returns the connection status.

        Returns:
            bool: True if database is accessible, False otherwise
        """
        try:
            logger.info("🔍 Executando health check do database")
            from sqlalchemy import text
            async with self.get_session() as session:
                result = await session.execute(text("SELECT 1"))
                is_healthy = result.scalar() == 1
                logger.info(f"✅ Database health check: {'OK' if is_healthy else 'FAIL'}")
                return is_healthy
        except Exception as e:
            logger.error(f"❌ Database health check failed: {str(e)}")
            return False

    async def close(self) -> None:
        """
        Close the database engine and cleanup connections.

        Properly closes all database connections and cleans up
        the connection pool to prevent resource leaks.
        """
        if self._engine:
            try:
                await self._engine.dispose()
                logger.info("✅ Database connection closed")
            except Exception as e:
                logger.error(f"❌ Erro ao fechar database: {str(e)}")

    @property
    def engine(self):
        """
        Get the database engine instance.

        Returns:
            AsyncEngine: SQLAlchemy async engine
        """
        return self._engine

    @property
    def session_factory(self):
        """
        Get the session factory for creating database sessions.

        Returns:
            async_sessionmaker: Session factory for creating database sessions
        """
        return self._session_factory