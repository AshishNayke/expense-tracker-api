import pytest
from pydantic import ValidationError

from awesome_project.config import Settings


def test_config_rejects_invalid_value():
    with pytest.raises(ValidationError):
        Settings(
            database_url="postgresql://user:pass@localhost/db",
            test_database_url="postgresql://user:pass@localhost/test_db",
            secret_key="some-secret-key",
            app_env="staging",
        )

@pytest.mark.parametrize("app_env",["development", "production"],)
def test_config_accepts_supported_values(app_env):
    settings = Settings(
        database_url="postgresql://user:pass@localhost/db",
        test_database_url="postgresql://user:pass@localhost/test_db",
        secret_key="some-secret-key",
        app_env=app_env,
    )

    assert settings.app_env == app_env