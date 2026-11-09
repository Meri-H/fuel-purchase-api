from logging.config import fileConfig

from alembic import context

from app import models
from app.database import Base, engine
from app.types import FixedDecimal


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def render_item(item_type, item, autogen_context):
    if item_type == "type" and isinstance(item, FixedDecimal):
        return "sa.BigInteger()"

    return False


with engine.connect() as connection:
    context.configure(
        connection=connection,
        target_metadata=Base.metadata,
        render_as_batch=True,
        render_item=render_item,
    )

    with context.begin_transaction():
        context.run_migrations()