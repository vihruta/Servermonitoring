import os
import yaml
from alerts.models import Thresholds
from pathlib import Path

from dotenv import load_dotenv

def load_monitoring_config(base_path: Path):
    CONFIG_PATH = base_path / "config.yaml"
    try:
        with CONFIG_PATH.open('r', encoding='utf-8') as file:
            config_data = yaml.safe_load(file)
        monitoring_data = config_data['monitoring']
        cpu_data = config_data['thresholds']['cpu']
        ram_data = config_data['thresholds']['ram']
        disk_data = config_data['thresholds']['disk']
        docker_data = config_data['docker']

        MONITORING_INTERVAL = monitoring_data['interval']
        CPU_TEMPERATURE_THRESHOLDS = Thresholds(**cpu_data['temperature'])
        CPU_USAGE_THRESHOLD = Thresholds(**cpu_data['usage'])
        RAM_THRESHOLDS = Thresholds(**ram_data)

        DISK_THRESHOLDS = {
            'temperature': Thresholds(**disk_data['temperature']),
            'usage': Thresholds(**disk_data['usage'])
        }

        MONITORED_CONTAINERS = set(docker_data['monitored_containers'])

        return MONITORING_INTERVAL, CPU_TEMPERATURE_THRESHOLDS, CPU_USAGE_THRESHOLD, RAM_THRESHOLDS, DISK_THRESHOLDS, MONITORED_CONTAINERS
    except Exception:
        raise RuntimeError('Thresholds is not set')


def load_logger_config(base_path: Path):
    CONFIG_PATH = base_path / "config.yaml"
    with CONFIG_PATH.open('r', encoding='utf-8') as file:
        config_data = yaml.safe_load(file)
    logger_data = config_data['logger']
    logging_level = logger_data['level']
    logging_format = logger_data['format']

    return logging_level, logging_format

BASE_DIR = Path(__file__).resolve().parent

LOGGING_LEVEL, LOGGING_FORMAT = load_logger_config(BASE_DIR)
MONITORING_INTERVAL, CPU_TEMPERATURE_THRESHOLDS, CPU_USAGE_THRESHOLD, RAM_THRESHOLDS, DISK_THRESHOLDS, MONITORED_CONTAINERS = load_monitoring_config(base_path=BASE_DIR)




ENV_PATH = BASE_DIR / ".env"
load_dotenv(ENV_PATH)

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
