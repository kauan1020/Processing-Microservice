import logging
from typing import Optional
from dataclasses import dataclass

import httpx

from infra.settings.settings import get_settings
from infra.databases.database_connection import DatabaseConnection

logger = logging.getLogger(__name__)


@dataclass
class ServiceConfig:
    user_service_url: str
    user_service_api_key: Optional[str] = None
    database_url: str = ""
    database_echo: bool = False
    max_retries: int = 3
    timeout: int = 10
    cache_ttl: int = 300


class UserServiceGateway:
    def __init__(self, user_service_url: str, timeout: int, retry_attempts: int, cache_ttl_seconds: int, api_key: str):
        self.base_url = user_service_url
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=timeout)
        self.api_key = api_key

    async def verify_user_exists(self, user_id: str) -> bool:
        response = await self.client.get(f"/users/profile/{user_id}")
        return response.status_code == 200

    async def health_check(self) -> dict:
        response = await self.client.get("/health")
        if response.status_code == 200:
            return {"healthy": True}
        return {"healthy": False}

    async def close(self):
        await self.client.aclose()


class MicroserviceManager:
    def __init__(self, config: ServiceConfig):
        self.config = config
        self._user_gateway: Optional[UserServiceGateway] = None
        self._db_connection: Optional[DatabaseConnection] = None
        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            return

        try:
            self._db_connection = DatabaseConnection(
                database_url=self.config.database_url,
                echo=self.config.database_echo
            )
            self._db_connection.initialize()

            self._user_gateway = UserServiceGateway(
                user_service_url=self.config.user_service_url,
                timeout=self.config.timeout,
                retry_attempts=self.config.max_retries,
                cache_ttl_seconds=self.config.cache_ttl,
                api_key=self.config.user_service_api_key
            )

            db_healthy = await self._db_connection.health_check()
            if db_healthy:
                logger.info("Banco de dados conectado")
            else:
                logger.warning("Banco de dados não está saudável")

            user_service_health = await self._user_gateway.health_check()
            if user_service_health["healthy"]:
                logger.info("Serviço de usuários conectado")
            else:
                logger.warning("Serviço de usuários com problemas")

            self._initialized = True
            logger.info("Gerenciador de microserviços inicializado")

        except Exception as e:
            logger.error(f"Falha ao inicializar gerenciador de microserviços: {str(e)}")
            self._initialized = True

    async def get_database_session(self):
        if not self._initialized:
            await self.initialize()

        if not self._db_connection:
            raise Exception("Conexão com banco de dados não foi inicializada")

        return self._db_connection.get_session()

    async def get_user_gateway(self) -> UserServiceGateway:
        if not self._initialized:
            await self.initialize()

        if not self._user_gateway:
            settings = get_settings()
            self._user_gateway = UserServiceGateway(
                user_service_url=settings.user_service.service_url,
                timeout=settings.user_service.timeout,
                retry_attempts=3,
                cache_ttl_seconds=300,
                api_key=settings.user_service.api_key
            )

        return self._user_gateway

    async def get_session_factory(self):
        if not self._initialized:
            await self.initialize()

        if not self._db_connection:
            raise Exception("Database connection not initialized")

        if hasattr(self._db_connection, 'async_session_factory'):
            return self._db_connection.async_session_factory
        elif hasattr(self._db_connection, 'session_factory'):
            return self._db_connection.session_factory
        else:
            raise Exception("Session factory not found in database connection")

    async def close(self) -> None:
        import asyncio

        tasks = []

        if self._user_gateway:
            tasks.append(self._user_gateway.close())

        if self._db_connection:
            tasks.append(self._db_connection.close())

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        self._initialized = False
        logger.info("Gerenciador de microserviços fechado")


_microservice_manager: Optional[MicroserviceManager] = None


def get_microservice_manager() -> MicroserviceManager:
    global _microservice_manager

    if _microservice_manager is None:
        settings = get_settings()

        config = ServiceConfig(
            user_service_url=settings.user_service.service_url,
            user_service_api_key=settings.user_service.api_key,
            database_url=settings.database.url,
            database_echo=settings.database.echo,
            max_retries=3,
            timeout=settings.user_service.timeout,
            cache_ttl=300
        )

        _microservice_manager = MicroserviceManager(config)

    return _microservice_manager


async def startup_handler():
    try:
        manager = get_microservice_manager()
        await manager.initialize()
        logger.info("Integração de microserviços inicializada no startup")
    except Exception as e:
        logger.warning(f"Problemas na inicialização: {str(e)}")


async def shutdown_handler():
    global _microservice_manager
    if _microservice_manager:
        try:
            await _microservice_manager.close()
            logger.info("Integração de microserviços fechada no shutdown")
        except Exception as e:
            logger.error(f"Erro durante o shutdown: {str(e)}")
        finally:
            _microservice_manager = None
