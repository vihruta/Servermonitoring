import httpx
import pytest

from aiogram.exceptions import TelegramNetworkError
from aiogram.methods import SendMessage

from alerts import state_store
from alerts.monitoring import network as network_monitor
from alerts.state_store import NetworkAccidentStore, AlertCooldownStore
from alerts.states import Alert, State
from config import InternetSettings
from models import HttpMetrics


def test_network_store_happy_path(monkeypatch):
    network_store = NetworkAccidentStore()
    current_time = 100

    def fake_monotonic():
        return current_time

    monkeypatch.setattr(
        state_store.time,
        'monotonic',
        fake_monotonic
    )

    network_store.start()

    assert network_store.started_at == 100

    current_time = 160

    network_store.start()
    assert network_store.started_at == 100
    assert network_store.confirmed is False
    assert network_store.notified is False

    network_store.confirm()
    network_store.notify()

    assert network_store.confirmed is True
    assert network_store.notified is True

    network_store.reset()
    assert network_store.started_at is None
    assert network_store.confirmed is False
    assert network_store.notified is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "first_send_fails",
    [False, True],
    ids=["successful_delivery", "retry_after_network_error"],
)
async def test_network_alert_delivery(monkeypatch, first_send_fails):
    current_time = 0.0
    attempts = []
    delivered = []

    def fake_monotonic():
        return current_time

    async def fake_network_check(client, service_settings):
        return HttpMetrics(
            service="internet",
            result_code=None,
            is_failed=True,
            error="Timeout error",
            duration_seconds=0.1,
        )

    async def fake_send_network_alert(
            bot,
            chat_id,
            status,
            problem_was_notified):
        attempts.append(current_time)

        if first_send_fails and len(attempts) == 1:
            raise TelegramNetworkError(
                method=SendMessage(chat_id=chat_id, text="Test"),
                message="Network unavailable",
            )

        delivered.append(status)

    monkeypatch.setattr(
        state_store.time, "monotonic", fake_monotonic
    )
    monkeypatch.setattr(
        network_monitor, "network_check", fake_network_check
    )
    monkeypatch.setattr(
        network_monitor, "send_network_alert", fake_send_network_alert
    )

    incident = NetworkAccidentStore()
    cooldown = AlertCooldownStore()
    settings = InternetSettings(
        url="https://example.com",
        timeout=10,
        expected_status={200},
        interval=60,
        failure_duration=120,
        cooldown=600,
    )

    async with httpx.AsyncClient() as client:
        async def run_check():
            await network_monitor.network_monitoring_metrics(
                client=client,
                network_incident=incident,
                network_settings=settings,
                cooldown=cooldown,
                bot=None,
                chat_id=123,
            )

        for timestamp in (0.0, 119.0):
            current_time = timestamp
            await run_check()

            assert attempts == []
            assert incident.started_at == 0.0
            assert incident.confirmed is False
            assert incident.notified is False

        current_time = 120.0
        await run_check()

        assert attempts == [120.0]
        assert incident.confirmed is True
        assert incident.notified == (not first_send_fails)
        assert incident.started_at == 0.0
        assert len(delivered) == (0 if first_send_fails else 1)

        current_time = 180.0
        await run_check()

        expected_attempts = (
            [120.0, 180.0] if first_send_fails else [120.0]
        )
        assert attempts == expected_attempts
        assert len(delivered) == 1
        assert incident.confirmed is True
        assert incident.notified is True
        assert incident.started_at == 0.0

        current_time = 181.0
        await run_check()

        assert attempts == expected_attempts
        assert len(delivered) == 1

    alert = delivered[0]["Network"]
    assert alert.status.alert == Alert.CRITICAL
    assert alert.status.state == State.CRITICAL
    assert alert.result_code is None
    assert alert.error == "Timeout error"
    assert alert.duration == (180.0 if first_send_fails else 120.0)


def test_network_store_check_duration(monkeypatch):
    network_store = NetworkAccidentStore()
    current_time = 100

    def fake_monotonic():
        return current_time

    monkeypatch.setattr(
        state_store.time,
        'monotonic',
        fake_monotonic
    )

    network_store.start()

    current_time = 160

    network_store.recover()
    current_time = 200
    network_store.recover()

    assert network_store.get_duration() == 60
    assert network_store.recovered_at == 160

    network_store.reset()

    assert network_store.recovered_at is None
    assert network_store.started_at is None
    assert network_store.get_duration() is None