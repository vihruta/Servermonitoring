import asyncio

import httpx
import pytest
from aiogram.exceptions import TelegramNetworkError
from aiogram.methods import SendMessage

from alerts import state_store
from alerts.monitoring import http as http_monitor
from alerts.state_store import AlertCooldownStore, IncidentStore, StateStore
from alerts.states import State
from config import HttpServiceSettings, HttpServicesSettings
from monitor import http_health


def service_settings():
    return HttpServicesSettings(monitored={
        name: HttpServiceSettings(
            url=f'https://{name}.example.com', expected_status={200}
        )
        for name in ('first', 'second')
    })


@pytest.mark.asyncio
@pytest.mark.parametrize('error_type', [httpx.ReadError, httpx.RemoteProtocolError])
async def test_http_health_continues_after_request_error(error_type):
    def handler(request):
        if request.url.host == 'first.example.com':
            raise error_type('Request failed', request=request)
        return httpx.Response(200)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        results = await http_health.http_health(client, service_settings())

    assert [result.service for result in results] == ['first', 'second']
    assert results[0].is_failed is True
    assert results[0].result_code is None
    assert results[0].error == 'Request error'
    assert results[1].is_failed is False


@pytest.mark.asyncio
async def test_http_health_logs_unexpected_error_and_checks_next_service(caplog):
    def handler(request):
        if request.url.host == 'first.example.com':
            raise ValueError('Unexpected failure')
        return httpx.Response(200)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        results = await http_health.http_health(client, service_settings())

    assert [result.service for result in results] == ['second']
    assert 'HTTP check failed | APP first' in caplog.text


@pytest.mark.asyncio
async def test_http_monitoring_continues_after_send_error(monkeypatch):
    current_time = 0
    monkeypatch.setattr(state_store.time, 'monotonic', lambda: current_time)
    store = StateStore()
    incident = IncidentStore()
    cooldown = AlertCooldownStore()
    attempts = []

    async def send_alert(bot, chat_id, status):
        service = next(iter(status))
        attempts.append(service)
        if service == 'first':
            raise TelegramNetworkError(
                method=SendMessage(chat_id=chat_id, text='Test'),
                message='Sending failed',
            )

    monkeypatch.setattr(http_monitor, 'send_http_alert', send_alert)
    transport = httpx.MockTransport(lambda request: httpx.Response(503))
    async with httpx.AsyncClient(transport=transport) as client:
        for current_time in (0, 120, 121):
            await http_monitor.http_monitoring(
                client=client, store=store, incident=incident,
                cooldown_timer=cooldown, bot=None, chat_id=123,
                http_settings=service_settings(),
            )

    assert attempts == ['first', 'second', 'first']
    assert store.get('http_check_first') == State.OK
    assert store.get('http_check_second') == State.WARNING
    assert cooldown.check('http_check_first', 600) is True
    assert cooldown.check('http_check_second', 600) is False


@pytest.mark.asyncio
async def test_http_health_does_not_swallow_cancellation():
    def handler(request):
        raise asyncio.CancelledError

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(asyncio.CancelledError):
            await http_health.http_health(client, service_settings())


def test_removing_missing_incident_is_safe():
    incident = IncidentStore()
    incident.remove('http_check_healthy')
    assert incident.get('http_check_healthy') is None
