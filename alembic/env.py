import asyncio
import os
import sys
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config, create_async_engine
from alembic import context

# Add the parent directory to the path so we can import our models
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# Import your models here
from infra.databases.models.video_job_model import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata


def get_database_url():
    """Get database URL from environment variables."""
    host = os.getenv("DATABASE_HOST", "localhost")
    port = os.getenv("DATABASE_PORT", "5432")
    name = os.getenv("DATABASE_NAME", "video_processing")
    user = os.getenv("DATABASE_USER", "postgres")
    password = os.getenv("DATABASE_PASSWORD", "password")

    # For alembic, we need the synchronous driver
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"


def get_async_database_url():
    """Get async database URL from environment variables."""
    host = os.getenv("DATABASE_HOST", "localhost")
    port = os.getenv("DATABASE_PORT", "5432")
    name = os.getenv("DATABASE_NAME", "video_processing")
    user = os.getenv("DATABASE_USER", "postgres")
    password = os.getenv("DATABASE_PASSWORD", "password")

    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{name}"


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with the given connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine."""
    # Get the database URL
    database_url = get_async_database_url()

    # Create async engine
    connectable = create_async_engine(
        database_url,
        poolclass=pool.NullPool,
        echo=False
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    # Check if we're running in async mode or sync mode
    try:
        # Try to run async migrations
        asyncio.run(run_async_migrations())
    except Exception as e:
        print(f"Async migration failed: {e}")
        print("Falling back to synchronous migration...")

        # Fallback to sync migration
        database_url = get_database_url()

        # Create sync engine using config
        config.set_main_option("sqlalchemy.url", database_url)

        connectable = config.attributes.get("connection", None)

        if connectable is None:
            # Create engine from config
            from sqlalchemy import create_engine
            connectable = create_engine(database_url, poolclass=pool.NullPool)

        with connectable.connect() as connection:
            do_run_migrations(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()