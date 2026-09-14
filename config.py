import os
import yaml
from alerts.models import Thresholds
from pathlib import Path

from dotenv import load_dotenv

def load_monitoring_config(base_path: Path):
    THRESHOLDS_PATH = base_path / "monitoring_config.yaml"
    with THRESHOLDS_PATH.open('r', encoding='utf-8') as file:
        config_data = yaml.safe_load(file)
    monitoring_data = config_data['monitoring']
    cpu_data = config_data['thresholds']['cpu']
    ram_data = config_data['thresholds']['ram']
    disk_data = config_data['thresholds']['disk']
    docker_data = config_data['docker']

    MONITORING_INTERVAL = monitoring_data['interval']
    CPU_THRESHOLDS = Thresholds(**cpu_data)

    RAM_THRESHOLDS = Thresholds(**ram_data)

    DISK_THRESHOLDS = {
        'temperature': Thresholds(**disk_data['temperature']),
        'usage': Thresholds(**disk_data['usage'])
    }

    MONITORED_CONTAINERS = set(docker_data['monitored_containers'])

    return MONITORING_INTERVAL,CPU_THRESHOLDS, RAM_THRESHOLDS, DISK_THRESHOLDS, MONITORED_CONTAINERS


BASE_DIR = Path(__file__).resolve().parent

MONITORING_INTERVAL, CPU_THRESHOLDS, RAM_THRESHOLDS, DISK_THRESHOLDS, MONITORED_CONTAINERS = load_monitoring_config(base_path=BASE_DIR)

if CPU_THRESHOLDS is None or RAM_THRESHOLDS is None or DISK_THRESHOLDS is None or MONITORED_CONTAINERS is None:
    raise RuntimeError('Thresholds is not set')



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
