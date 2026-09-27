from pathlib import Path
import pytest
import yaml
from pydantic import ValidationError

from config import Settings, get_settings


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_example_config_can_be_loaded(tmp_path, monkeypatch):
    example_yaml_config = PROJECT_ROOT / "config.example.yaml"
    test_yaml_config = tmp_path / "config.yaml"
    test_yaml_config.write_text(
        example_yaml_config.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    example_env_config = PROJECT_ROOT / ".env.example"
    test_env_config = tmp_path / ".env"
    test_env_config.write_text(
        example_env_config.read_text(
            encoding="utf-8"),
            encoding="utf-8"
    )
    monkeypatch.delenv('TOKEN', raising=False)
    monkeypatch.delenv('ALLOWED_USER', raising=False)
    monkeypatch.delenv('ALERTS_CHAT_ID', raising=False)

    settings = get_settings(tmp_path)

    assert isinstance(settings, Settings)

    assert settings.logger.level == 'INFO'

    assert settings.telegram.token == "test-token"
    assert settings.telegram.allowed_users == {111, 222}
    assert settings.telegram.alert_chat_id == 333

    assert settings.monitoring.interval == 60

    assert settings.thresholds.cpu.temperature.warning == 85
    assert settings.thresholds.cpu.usage.warning == 85

    assert settings.thresholds.ram.warning == 85

    assert settings.thresholds.disk.temperature.warning == 65
    assert settings.thresholds.disk.usage.warning == 80

    assert "vaultwarden" in settings.docker.monitored_containers


def test_invalid_monitoring_interval(tmp_path, monkeypatch):
    monkeypatch.delenv("TOKEN", raising=False)
    monkeypatch.delenv("ALLOWED_USER", raising=False)
    monkeypatch.delenv("ALERTS_CHAT_ID", raising=False)

    example_config = PROJECT_ROOT / "config.example.yaml"
    config_data = yaml.safe_load(
        example_config.read_text(encoding="utf-8")
    )

    config_data["monitoring"]["interval"] = "abc"

    test_config = tmp_path / "config.yaml"
    test_config.write_text(
        yaml.safe_dump(config_data, allow_unicode=True),
        encoding="utf-8",
    )

    test_env = tmp_path / ".env"
    test_env.write_text(
        "TOKEN=test-token\n"
        "ALLOWED_USER=111,222\n"
        "ALERTS_CHAT_ID=333\n",
        encoding="utf-8",
    )

    with pytest.raises(ValidationError) as error:
        get_settings(tmp_path)

    assert "monitoring.interval" in str(error.value)


def test_token_is_required(tmp_path, monkeypatch):
    monkeypatch.delenv("TOKEN", raising=False)
    monkeypatch.delenv("ALLOWED_USER", raising=False)
    monkeypatch.delenv("ALERTS_CHAT_ID", raising=False)

    example_config = PROJECT_ROOT / "config.example.yaml"
    test_config = tmp_path / "config.yaml"
    test_config.write_text(
        example_config.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    test_env = tmp_path / ".env"
    test_env.write_text(
        "ALLOWED_USER=111,222\n"
        "ALERTS_CHAT_ID=333\n",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="TOKEN is not set"):
        get_settings(tmp_path)