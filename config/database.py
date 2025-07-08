from urllib.parse import quote_plus
import os


class DatabaseConfig:
    """Configuração segura para conexão com banco de dados."""

    @staticmethod
    def get_postgresql_url(async_driver: bool = True) -> str:
        """
        Gera URL para PostgreSQL com driver apropriado.

        Args:
            async_driver: Se True, usa asyncpg; se False, usa psycopg2
        """
        db_host = os.getenv("DATABASE_HOST", "localhost")
        db_port = os.getenv("DATABASE_PORT", "5432")
        db_name = os.getenv("DATABASE_NAME", "video_processing")
        db_user = os.getenv("DATABASE_USER", "postgres")
        db_password = os.getenv("DATABASE_PASSWORD", "password")

        # Escape da senha
        escaped_password = quote_plus(db_password)

        if async_driver:
            # Para operações assíncronas
            driver = "postgresql+asyncpg"
        else:
            # Para operações síncronas (como Alembic)
            driver = "postgresql+psycopg2"

        return f"{driver}://{db_user}:{escaped_password}@{db_host}:{db_port}/{db_name}"

    @staticmethod
    def get_mysql_url(async_driver: bool = True) -> str:
        """Gera URL para MySQL com driver apropriado."""
        db_host = os.getenv("DATABASE_HOST", "localhost")
        db_port = os.getenv("DATABASE_PORT", "3306")
        db_name = os.getenv("DATABASE_NAME", "video_processing")
        db_user = os.getenv("DATABASE_USER", "root")
        db_password = os.getenv("DATABASE_PASSWORD", "root")

        escaped_password = quote_plus(db_password)

        if async_driver:
            driver = "mysql+aiomysql"
        else:
            driver = "mysql+pymysql"

        return f"{driver}://{db_user}:{escaped_password}@{db_host}:{db_port}/{db_name}"

    @staticmethod
    def get_sqlite_url(async_driver: bool = True) -> str:
        """Gera URL para SQLite."""
        db_path = os.getenv("DATABASE_PATH", "./video_processing.db")

        if async_driver:
            driver = "sqlite+aiosqlite"
        else:
            driver = "sqlite"

        return f"{driver}:///{db_path}"
