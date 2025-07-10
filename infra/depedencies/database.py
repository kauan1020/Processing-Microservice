"""
Dependências de banco de dados e serviços integrados.
Substitua o conteúdo do seu arquivo infra/depedencies/database.py por este.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from typing import AsyncGenerator

from infra.integration.microservice_manager import get_microservice_manager
from infra.gateways.user_service_gateway import UserServiceGateway


async def get_database_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependência para obter sessão de banco de dados.
    """
    manager = get_microservice_manager()
    async with await manager.get_database_session() as session:
        yield session


async def get_user_service() -> UserServiceGateway:
    """
    Dependência para obter gateway do serviço de usuários.
    """
    manager = get_microservice_manager()
    return await manager.get_user_gateway()


def get_session_factory(self):
    """
    Get the session factory for repositories that need it.

    Returns:
        Callable: Session factory function that creates AsyncSession instances
    """
    if not self.async_session_factory:
        raise Exception("Database not initialized - session factory not available")

    return self.async_session_factory