from alembic import command

from tests.conftest import alembic_config


def test_models_and_migrations_are_in_sync(postgres_url: str) -> None:
    """Fails when a model changes without a matching Alembic migration."""
    command.check(alembic_config(postgres_url))


def test_downgrade_to_base_and_back(postgres_url: str) -> None:
    cfg = alembic_config(postgres_url)
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
