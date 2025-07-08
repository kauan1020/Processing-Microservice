import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from infra.integration.microservice_manager import (
    MicroserviceManager,
    ServiceConfig,
    get_microservice_manager,
    startup_handler,
    shutdown_handler
)


class TestServiceConfig:

    def test_service_config_creation_with_required_fields_should_initialize_correctly(self):
        config = ServiceConfig(
            user_service_url="http://localhost:8002",
            database_url="postgresql://test:test@localhost/test"
        )

        assert config.user_service_url == "http://localhost:8002"
        assert config.database_url == "postgresql://test:test@localhost/test"
        assert config.user_service_api_key is None
        assert config.database_echo is False
        assert config.max_retries == 3
        assert config.timeout == 10
        assert config.cache_ttl == 300

    def test_service_config_creation_with_all_fields_should_initialize_correctly(self):
        config = ServiceConfig(
            user_service_url="http://localhost:8002",
            user_service_api_key="test-key",
            database_url="postgresql://test:test@localhost/test",
            database_echo=True,
            max_retries=5,
            timeout=30,
            cache_ttl=600
        )

        assert config.user_service_api_key == "test-key"
        assert config.database_echo is True
        assert config.max_retries == 5
        assert config.timeout == 30
        assert config.cache_ttl == 600


class TestMicroserviceManager:

    @pytest.fixture
    def service_config(self):
        return ServiceConfig(
            user_service_url="http://localhost:8002",
            user_service_api_key="test-api-key",
            database_url="postgresql://test:test@localhost/test",
            database_echo=False,
            max_retries=3,
            timeout=10,
            cache_ttl=300
        )

    @pytest.fixture
    def mock_database_connection(self):
        db_connection = Mock()
        db_connection.initialize = Mock()
        db_connection.health_check = AsyncMock(return_value=True)
        db_connection.close = AsyncMock()
        db_connection.get_session = Mock()
        db_connection.async_session_factory = Mock()
        return db_connection

    @pytest.fixture
    def mock_user_gateway(self):
        gateway = Mock()
        gateway.health_check = AsyncMock(return_value={"healthy": True})
        gateway.close = AsyncMock()
        return gateway

    @pytest.fixture
    def manager(self, service_config):
        return MicroserviceManager(service_config)

    @pytest.mark.asyncio
    async def test_initialize_with_healthy_services_should_complete_successfully(
            self, manager, mock_database_connection, mock_user_gateway
    ):
        with patch('infra.integration.microservice_manager.DatabaseConnection', return_value=mock_database_connection), \
                patch('infra.integration.microservice_manager.UserServiceGateway', return_value=mock_user_gateway):
            await manager.initialize()

            assert manager._initialized is True
            mock_database_connection.initialize.assert_called_once()
            mock_user_gateway.health_check.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_with_unhealthy_database_should_continue_with_warning(
            self, manager, mock_database_connection, mock_user_gateway
    ):
        mock_database_connection.health_check.return_value = False

        with patch('infra.integration.microservice_manager.DatabaseConnection', return_value=mock_database_connection), \
                patch('infra.integration.microservice_manager.UserServiceGateway', return_value=mock_user_gateway):
            await manager.initialize()

            assert manager._initialized is True

    @pytest.mark.asyncio
    async def test_initialize_with_user_service_error_should_continue_gracefully(
            self, manager, mock_database_connection, mock_user_gateway
    ):
        mock_user_gateway.health_check.side_effect = Exception("Service unavailable")

        with patch('infra.integration.microservice_manager.DatabaseConnection', return_value=mock_database_connection), \
                patch('infra.integration.microservice_manager.UserServiceGateway', return_value=mock_user_gateway):
            await manager.initialize()

            assert manager._initialized is True

    @pytest.mark.asyncio
    async def test_initialize_with_critical_error_should_still_mark_as_initialized(
            self, manager, mock_database_connection
    ):
        with patch('infra.integration.microservice_manager.DatabaseConnection',
                   side_effect=Exception("Critical error")):
            await manager.initialize()

            assert manager._initialized is True

    @pytest.mark.asyncio
    async def test_initialize_already_initialized_should_return_early(self, manager):
        manager._initialized = True

        with patch('infra.integration.microservice_manager.DatabaseConnection') as mock_db_class:
            await manager.initialize()

            mock_db_class.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_database_session_should_initialize_if_needed_and_return_session(
            self, manager, mock_database_connection
    ):
        mock_session = Mock()
        mock_database_connection.get_session.return_value = mock_session

        with patch('infra.integration.microservice_manager.DatabaseConnection', return_value=mock_database_connection), \
                patch('infra.integration.microservice_manager.UserServiceGateway'):
            result = await manager.get_database_session()

            assert result == mock_session
            assert manager._initialized is True

    @pytest.mark.asyncio
    async def test_get_database_session_without_connection_should_raise_exception(self, manager):
        manager._initialized = True
        manager._db_connection = None

        with pytest.raises(Exception, match="Conexão com banco de dados não foi inicializada"):
            await manager.get_database_session()

    @pytest.mark.asyncio
    async def test_get_user_gateway_should_initialize_if_needed_and_return_gateway(
            self, manager, mock_user_gateway
    ):
        with patch('infra.integration.microservice_manager.DatabaseConnection'), \
                patch('infra.integration.microservice_manager.UserServiceGateway', return_value=mock_user_gateway):
            result = await manager.get_user_gateway()

            assert result == mock_user_gateway
            assert manager._initialized is True

    @pytest.mark.asyncio
    async def test_get_user_gateway_without_gateway_should_create_new_one(self, manager):
        manager._initialized = True
        manager._user_gateway = None

        with patch('infra.integration.microservice_manager.get_settings') as mock_settings, \
                patch('infra.integration.microservice_manager.UserServiceGateway') as mock_gateway_class:
            mock_settings.return_value.user_service.service_url = "http://localhost:8002"
            mock_settings.return_value.user_service.timeout = 30
            mock_settings.return_value.user_service.api_key = "test-key"

            mock_gateway = Mock()
            mock_gateway_class.return_value = mock_gateway

            result = await manager.get_user_gateway()

            assert result == mock_gateway
            mock_gateway_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_session_factory_should_return_session_factory(
            self, manager, mock_database_connection
    ):
        mock_session_factory = Mock()
        mock_database_connection.async_session_factory = mock_session_factory

        with patch('infra.integration.microservice_manager.DatabaseConnection', return_value=mock_database_connection), \
                patch('infra.integration.microservice_manager.UserServiceGateway'):
            result = await manager.get_session_factory()

            assert result == mock_session_factory

    @pytest.mark.asyncio
    async def test_get_session_factory_with_session_factory_attribute_should_return_it(
            self, manager, mock_database_connection
    ):
        mock_session_factory = Mock()
        mock_database_connection.session_factory = mock_session_factory
        del mock_database_connection.async_session_factory

        with patch('infra.integration.microservice_manager.DatabaseConnection', return_value=mock_database_connection), \
                patch('infra.integration.microservice_manager.UserServiceGateway'):
            result = await manager.get_session_factory()

            assert result == mock_session_factory

    @pytest.mark.asyncio
    async def test_get_session_factory_without_factory_should_raise_exception(
            self, manager, mock_database_connection
    ):
        del mock_database_connection.async_session_factory
        del mock_database_connection.session_factory

        with patch('infra.integration.microservice_manager.DatabaseConnection', return_value=mock_database_connection), \
                patch('infra.integration.microservice_manager.UserServiceGateway'):
            with pytest.raises(Exception, match="Session factory not found"):
                await manager.get_session_factory()

    @pytest.mark.asyncio
    async def test_get_session_factory_without_connection_should_raise_exception(self, manager):
        manager._initialized = True
        manager._db_connection = None

        with pytest.raises(Exception, match="Database connection not initialized"):
            await manager.get_session_factory()

    @pytest.mark.asyncio
    async def test_close_should_cleanup_all_resources(
            self, manager, mock_database_connection, mock_user_gateway
    ):
        manager._initialized = True
        manager._db_connection = mock_database_connection
        manager._user_gateway = mock_user_gateway

        await manager.close()

        mock_user_gateway.close.assert_called_once()
        mock_database_connection.close.assert_called_once()
        assert manager._initialized is False

    @pytest.mark.asyncio
    async def test_close_without_resources_should_complete_gracefully(self, manager):
        manager._initialized = True
        manager._db_connection = None
        manager._user_gateway = None

        await manager.close()

        assert manager._initialized is False

    @pytest.mark.asyncio
    async def test_close_with_exceptions_should_continue_cleanup(
            self, manager, mock_database_connection, mock_user_gateway
    ):
        manager._initialized = True
        manager._db_connection = mock_database_connection
        manager._user_gateway = mock_user_gateway

        mock_user_gateway.close.side_effect = Exception("Close error")
        mock_database_connection.close.side_effect = Exception("Close error")

        await manager.close()

        assert manager._initialized is False


class TestGlobalManagerFunctions:

    def test_get_microservice_manager_should_return_singleton_instance(self):
        with patch('infra.integration.microservice_manager.get_settings') as mock_settings:
            mock_settings.return_value.user_service.service_url = "http://localhost:8002"
            mock_settings.return_value.user_service.api_key = "test-key"
            mock_settings.return_value.database.url = "postgresql://test:test@localhost/test"
            mock_settings.return_value.database.echo = False
            mock_settings.return_value.user_service.timeout = 30

            manager1 = get_microservice_manager()
            manager2 = get_microservice_manager()

            assert manager1 is manager2
            assert isinstance(manager1, MicroserviceManager)

    @pytest.mark.asyncio
    async def test_startup_handler_should_initialize_manager(self):
        with patch('infra.integration.microservice_manager.get_microservice_manager') as mock_get_manager:
            mock_manager = Mock()
            mock_manager.initialize = AsyncMock()
            mock_get_manager.return_value = mock_manager

            await startup_handler()

            mock_manager.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_startup_handler_with_exception_should_log_warning_and_continue(self):
        with patch('infra.integration.microservice_manager.get_microservice_manager') as mock_get_manager:
            mock_manager = Mock()
            mock_manager.initialize = AsyncMock(side_effect=Exception("Initialization failed"))
            mock_get_manager.return_value = mock_manager

            # Should not raise exception
            await startup_handler()

            mock_manager.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_handler_should_close_manager_and_reset_global(self):
        with patch('infra.integration.microservice_manager.get_microservice_manager') as mock_get_manager:
            mock_manager = Mock()
            mock_manager.close = AsyncMock()
            mock_get_manager.return_value = mock_manager

            # Set global manager
            with patch('infra.integration.microservice_manager._microservice_manager', mock_manager):
                await shutdown_handler()

                mock_manager.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_handler_with_exception_should_handle_gracefully(self):
        with patch('infra.integration.microservice_manager._microservice_manager') as mock_manager:
            mock_manager.close = AsyncMock(side_effect=Exception("Close failed"))

            # Should not raise exception
            await shutdown_handler()

            mock_manager.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_handler_without_manager_should_complete_gracefully(self):
        with patch('infra.integration.microservice_manager._microservice_manager', None):
            # Should not raise exception
            await shutdown_handler()

    def test_microservice_manager_config_validation(self):
        """Test that the manager properly validates and uses the config"""
        config = ServiceConfig(
            user_service_url="http://test-service:8002",
            user_service_api_key="secret-key",
            database_url="postgresql://user:pass@db:5432/mydb",
            database_echo=True,
            max_retries=5,
            timeout=25,
            cache_ttl=600
        )

        manager = MicroserviceManager(config)

        assert manager.config.user_service_url == "http://test-service:8002"
        assert manager.config.user_service_api_key == "secret-key"
        assert manager.config.database_url == "postgresql://user:pass@db:5432/mydb"
        assert manager.config.database_echo is True
        assert manager.config.max_retries == 5
        assert manager.config.timeout == 25
        assert manager.config.cache_ttl == 600
        assert manager._initialized is False