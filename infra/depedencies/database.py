"""
Dependências de banco de dados e serviços integrados.
Substitua o conteúdo do seu arquivo infra/depedencies/database.py por este.
"""
import os

from sqlalchemy.ext.asyncio import AsyncSession
from typing import AsyncGenerator
from infra.settings.settings import get_settings
from infra.integration.microservice_manager import get_microservice_manager
from infra.gateways.user_service_gateway import UserServiceGateway


async def get_database_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependência para obter sessão de banco de dados.
    """
    manager = get_microservice_manager()
    async with await manager.get_database_session() as session:
        yield session


async def get_user_service():
    """
    Obter instância do UserServiceGateway com configuração correta
    """
    settings = get_settings()

    # IMPORTANTE: Verificar qual URL usar
    # Se o teste direto funciona com auth-service:8000, talvez seja esse o correto
    user_service_url = os.getenv("USER_SERVICE_URL", "http://auth-service:8000")

    print(f"[DEBUG] Configurando UserServiceGateway com URL: {user_service_url}")

    return UserServiceGateway(
        user_service_url=user_service_url,
        timeout=30,
        retry_attempts=3,
        cache_ttl_seconds=300,
        api_key="6CQf0vIiqeMYWbZCE8Q0LH4D73p9j3ms"
    )



def get_session_factory(self):
    """
    Get the session factory for repositories that need it.

    Returns:
        Callable: Session factory function that creates AsyncSession instances
    """
    if not self.async_session_factory:
        raise Exception("Database not initialized - session factory not available")

    return self.async_session_factory
