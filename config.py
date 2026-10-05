import os
import yaml
from alerts.models import Thresholds
from pathlib import Path
from pydantic import BaseModel, Field

from dotenv import load_dotenv

class MonitoringSettings(BaseModel):
    interval: int = Field(default=60, gt=0)

class LoggerSettings(BaseModel):
    level: str
    format: str

class DockerSettings(BaseModel):
    monitored_containers: set[str]
    cooldown: int = Field(default=600, ge=0)

class HttpServiceSettings(BaseModel):
    url: str
    timeout: float = Field(default=10.0, gt=0)
    expected_status: set[int] = Field(min_length=1)

class HttpServicesSettings(BaseModel):
    interval: float = Field(default=60.0, ge=0)
    failure_duration: float = Field(default=120, gt=0)
    cooldown: float = Field(default=600.0, gt=0)
    monitored: dict[str, HttpServiceSettings]

class InternetSettings(HttpServiceSettings):
    interval: float = Field(default=60.0, ge=0)
    failure_duration: float = Field(default=120.0, ge=0)
    cooldown: float = Field(default=600.0, ge=0)

class TelegramSettings(BaseModel):
    token: str
    allowed_users: set[int]
    alert_chat_id: int

class CpuThresholds(BaseModel):
    temperature: Thresholds
    usage: Thresholds

class DiskThresholds(BaseModel):
    temperature: Thresholds
    usage: Thresholds

class ThresholdSettings(BaseModel):
    cpu: CpuThresholds
    disk: DiskThresholds
    ram: Thresholds

class TimeOutSettings(BaseModel):
    smartctl: int = Field(default=10, gt=0)
    lsblk: int = Field(default=5, gt=0)
    docker: int = Field(default=10, gt=0)

class Settings(BaseModel):
    monitoring: MonitoringSettings
    logger: LoggerSettings
    docker: DockerSettings
    telegram: TelegramSettings
    thresholds: ThresholdSettings
    timeouts: TimeOutSettings
    http_services: HttpServicesSettings
    internet: InternetSettings



def get_yaml_config(base_path: Path):
    config_path = base_path / "config.yaml"
    with config_path.open('r', encoding='utf-8') as file:
        yaml_data = yaml.safe_load(file)

    if yaml_data is None:
        raise ValueError(f"Файл конфигурации {config_path} пуст или содержит null")

    if not isinstance(yaml_data, dict):
        raise ValueError(
            f"В файле {config_path} ожидаются разделы с настройками, "
            "а не список или одиночное значение"
        )

    return yaml_data
    

def get_env_config(base_path: Path):
    env_path = base_path / ".env"
    load_dotenv(env_path)
    token_value = os.getenv('TOKEN')
    allowed_user_raw = os.getenv('ALLOWED_USER')
    alert_chat_id_value = os.getenv('ALERTS_CHAT_ID')

    if token_value is None:
        raise RuntimeError("TOKEN is not set")

    if allowed_user_raw is not None:
        allowed_users = {
            int(user_id) for user_id in allowed_user_raw.split(',')
            if user_id
        }
    else:
        raise RuntimeError('Allowed user is not set')

    if alert_chat_id_value is None:
        raise RuntimeError('Alerts chat id is not set')

    alert_chat_id: int = int(alert_chat_id_value)
    token: str = token_value

    return {'token': token, 
            'allowed_users': allowed_users, 
            'alert_chat_id': alert_chat_id}


def get_settings(base_path: Path) -> Settings:
    data = get_yaml_config(base_path)
    data['telegram'] = get_env_config(base_path)

    return Settings.model_validate(data)


