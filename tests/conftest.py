from pathlib import Path

import pytest
import yaml

from config import Settings


@pytest.fixture
def app_settings():
    """Настройки без чтения настоящего токена и .env."""
    path = Path(__file__).resolve().parents[1] / 'config.example.yaml'
    data = yaml.safe_load(path.read_text(encoding='utf-8'))
    data['telegram'] = {
        'token': 'test-token',
        'allowed_users': {123},
        'alert_chat_id': 123,
    }
    return Settings.model_validate(data)
