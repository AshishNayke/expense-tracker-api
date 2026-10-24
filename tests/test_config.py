import pytest
from pydantic import ValidationError

from awesome_project.config import Settings

VALID_SECRET_KEY = "a" * 64


def test_config_rejects_invalid_value():
    with pytest.raises(ValidationError):
        Settings(
            database_url="postgresql://user:pass@localhost/db",
            secret_key=VALID_SECRET_KEY,
            app_env="staging",
        )


@pytest.mark.parametrize(
    "app_env",
    ["development", "production"],
)
def test_config_accepts_supported_values(app_env):
    settings = Settings(
        database_url="postgresql://user:pass@localhost/db",
        secret_key=VALID_SECRET_KEY,
        app_env=app_env,
    )

    assert settings.app_env == app_env


def test_production_settings_do_not_require_test_database_url(monkeypatch):
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)

    settings = Settings(
        _env_file=None,
        database_url="postgresql://user:pass@localhost/db",
        secret_key=VALID_SECRET_KEY,
        app_env="production",
    )

    assert settings.app_env == "production"
    assert not hasattr(settings, "test_database_url")
