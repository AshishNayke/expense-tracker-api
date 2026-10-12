import pytest
from pydantic import ValidationError

from awesome_project.config import Settings


def test_config_rejects_invalid_value():
    with pytest.raises(ValidationError):
        Settings(
            database_url="postgresql://user:pass@localhost/db",
            test_database_url="postgresql://user:pass@localhost/test_db",
            secret_key="f2bb79026bf9185619823ec2c1a4e4a861267417d24a1654dd3b20d6674e75251950089ed0414b5acc6fbde567a02197ea12cfe1983996c992973283b1622ed2",
            app_env="staging",
        )

@pytest.mark.parametrize("app_env",["development", "production"],)
def test_config_accepts_supported_values(app_env):
    settings = Settings(
        database_url="postgresql://user:pass@localhost/db",
        test_database_url="postgresql://user:pass@localhost/test_db",
        secret_key="1950089ed0414b5acc6fbde567a02197ea12cfe1983996c992973283b1622ed2f2bb79026bf9185619823ec2c1a4e4a861267417d24a1654dd3b20d6674e7525",
        app_env=app_env,
    )

    assert settings.app_env == app_env