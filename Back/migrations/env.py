from logging.config import fileConfig

from alembic import context

from app.db.base import Base
from app.models import MODELS  # Registers every table, including auth and support.

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)
target_metadata = Base.metadata


if context.is_offline_mode():
    # Offline inspection requires neither credentials nor a live database.
    context.configure(
        dialect_name='postgresql',
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    from app.db.session import engine
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()
