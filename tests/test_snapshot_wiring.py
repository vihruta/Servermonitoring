import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import main as app
from alerts import monitor
from alerts.monitoring import network
from alerts.state_store import AlertCooldownStore, HttpSnapshotStore, NetworkAccidentStore, SmartSnapshotStore
from models import HttpMetrics
from telegram import handlers


@pytest.mark.asyncio
@pytest.mark.parametrize('connection', ['smart_commands', 'network_loop'])
async def test_main_shares_snapshot_stores(monkeypatch, app_settings, connection):
    loop_arguments = {}
    polling_arguments = {}

    async def fake_smart_loop(**kwargs):
        loop_arguments['smart'] = kwargs

    async def fake_network_loop(**kwargs):
        loop_arguments['network'] = kwargs

    async def fake_polling(bot, **kwargs):
        polling_arguments.update(kwargs)
        # Дать созданным в main задачам один раз выполнить свои функции.
        await asyncio.sleep(0)

    dp = SimpleNamespace(include_router=lambda router: None,
                         start_polling=fake_polling)
    router = SimpleNamespace(message=SimpleNamespace(filter=lambda value: None))
    monkeypatch.setattr(app, 'start_router', router)
    monkeypatch.setattr(app, 'get_settings', lambda path: app_settings)
    monkeypatch.setattr(app, 'create_bot', lambda token: (None, dp))
    monkeypatch.setattr(app, 'setup_commands', AsyncMock())
    monkeypatch.setattr(app, 'monitoring_loop', AsyncMock())
    monkeypatch.setattr(app, 'http_monitoring_loop', AsyncMock())
    monkeypatch.setattr(app, 'smart_monitoring_loop', fake_smart_loop)
    monkeypatch.setattr(app, 'network_monitoring_loop', fake_network_loop)

    await app.main()

    if connection == 'smart_commands':
        assert isinstance(polling_arguments['smart_store'], SmartSnapshotStore)
        assert polling_arguments['smart_store'] is loop_arguments['smart']['smart_store']
    else:
        assert loop_arguments['network'].get('http_store') is polling_arguments['http_store']


@pytest.mark.asyncio
async def test_network_loop_records_first_snapshot(monkeypatch, app_settings):
    snapshots = HttpSnapshotStore()
    result = HttpMetrics(service='Internet', result_code=200, is_failed=False,
                         error=None, duration_seconds=0.1)
    monkeypatch.setattr(network, 'network_check', AsyncMock(return_value=result))

    async def stop_after_first_check(delay):
        raise asyncio.CancelledError

    monkeypatch.setattr(monitor.asyncio, 'sleep', stop_after_first_check)
    with pytest.raises(asyncio.CancelledError):
        await monitor.network_monitoring_loop(
            client=None,
            http_store=snapshots,
            network_incident=NetworkAccidentStore(),
            network_settings=app_settings.internet,
            cooldown=AlertCooldownStore(),
            bot=None,
            chat_id=123,
        )

    assert snapshots.get('Internet').metrics == result


@pytest.mark.asyncio
async def test_network_command_before_first_measurement(app_settings):
    message = SimpleNamespace(answer=AsyncMock())
    await handlers.cmd_network(message=message, settings=app_settings,
                               http_store=HttpSnapshotStore())
    message.answer.assert_awaited_once()
    assert 'Данных пока нет' in message.answer.await_args.args[0]
