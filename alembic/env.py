import os
from logging.config import fileConfig
from sqlalchemy import engine_from_config, create_engine  # Add create_engine
from sqlalchemy import pool
from alembic import context

# Import your models here
from src.models.database_models import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""

    # 1. Get the URL from environment variable or fallback
    url = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:a2bf9c79@localhost:5432/internship-project"
    )

    # 2. Create the engine manually
    connectable = create_engine(url)

    # 3. Connect and run migrations
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


# Ensure the rest of the file stays as generated (calls run_migrations_offline/online)
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()