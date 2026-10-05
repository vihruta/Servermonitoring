import pytest
import httpx

from monitor import http_health
from config import HttpServiceSettings, HttpServicesSettings
from alerts.models import HttpAlertData
from alerts import monitor



@pytest.mark.asyncio
async def test_http_service_check_happypath(monkeypatch: pytest.MonkeyPatch):
    current_time = 100

    def fake_handler(request: httpx.Request) -> httpx.Response:
        nonlocal current_time
        current_time += 1
        return httpx.Response(status_code=200)

    transport = httpx.MockTransport(fake_handler)

    service = 'test_app'
    settings = HttpServiceSettings(
        url='https://test_app.com',
        timeout=10,
        expected_status={200}
    )

    def fake_monotonic():
        return current_time

    monkeypatch.setattr(
        http_health.time,
        "monotonic",
        fake_monotonic
    )

    async with httpx.AsyncClient(transport=transport) as client:
        result = await http_health.http_service_check(  
            service=service,
            client=client,
            service_settings = settings,
        )

    assert result.service == service
    assert result.result_code == 200
    assert result.is_failed is False
    assert result.error is None
    assert result.duration_seconds == 1


@pytest.mark.asyncio
async def test_http_service_return_code_503(monkeypatch: pytest.MonkeyPatch):
    current_time = 100

    def fake_handler(request: httpx.Request) -> httpx.Response:
        nonlocal current_time
        current_time += 1
        return httpx.Response(status_code=503)

    transport = httpx.MockTransport(fake_handler)

    service = 'test_app'
    settings = HttpServiceSettings(
        url='https://test_app.com',
        timeout=10,
        expected_status={200}
    )

    def fake_monotonic():
        return current_time

    monkeypatch.setattr(
        http_health.time,
        "monotonic",
        fake_monotonic
    )

    async with httpx.AsyncClient(transport=transport) as client:
        result = await http_health.http_service_check(  
            service=service,
            client=client,
            service_settings = settings,
        )
    error_str = 'Unexpected HTTP status'

    assert result.service == service
    assert result.result_code == 503
    assert result.is_failed is True
    assert result.error == error_str
    assert result.duration_seconds == 1

@pytest.mark.asyncio
async def test_http_service_return_timeout(monkeypatch: pytest.MonkeyPatch):
    current_time = 100

    def fake_handler(request: httpx.Request) -> httpx.Response:
        nonlocal current_time
        current_time += 1
        raise httpx.ReadTimeout(message='Timeout',
                                request=request)

    transport = httpx.MockTransport(fake_handler)

    service = 'test_app'
    settings = HttpServiceSettings(
        url='https://test_app.com',
        timeout=10,
        expected_status={200}
    )

    def fake_monotonic():
        return current_time

    monkeypatch.setattr(
        http_health.time,
        "monotonic",
        fake_monotonic
    )

    async with httpx.AsyncClient(transport=transport) as client:
        result = await http_health.http_service_check(  
            service=service,
            client=client,
            service_settings = settings,
        )
    error_str = 'Timeout error'

    assert result.service == service
    assert result.result_code == None
    assert result.is_failed is True
    assert result.error is not None
    assert error_str == result.error
    assert result.duration_seconds == 1

@pytest.mark.asyncio
async def test_http_service_connection_error(monkeypatch: pytest.MonkeyPatch):
    current_time = 100

    def fake_handler(request: httpx.Request) -> httpx.Response:
        nonlocal current_time
        current_time += 1
        raise httpx.ConnectError(
            message='error',
            request=request
        )

    transport = httpx.MockTransport(fake_handler)

    service = 'test_app'
    settings = HttpServiceSettings(
        url='https://test_app.com',
        timeout=10,
        expected_status={200}
    )

    def fake_monotonic():
        return current_time

    monkeypatch.setattr(
        http_health.time,
        "monotonic",
        fake_monotonic
    )


    async with httpx.AsyncClient(transport=transport) as client:
        result = await http_health.http_service_check(  
            service=service,
            client=client,
            service_settings = settings,
        )
    error_str = 'Connection error'

    assert result.service == service
    assert result.result_code == None
    assert result.is_failed is True
    assert result.error is not None
    assert error_str == result.error
    assert result.duration_seconds == 1


@pytest.mark.asyncio
async def test_http_health_continues_after_connection_error(monkeypatch: pytest.MonkeyPatch):
    current_time = 100

    def fake_handler(request: httpx.Request) -> httpx.Response:
        nonlocal current_time
        if request.url == 'https://test_app.com':
            current_time += 1
            raise httpx.ConnectError(
                message='Connection error',
                request=request
            )
        
        elif request.url == 'https://second_test_app.com':
            code = 200
            current_time += 2
        else:
            raise AssertionError

        return httpx.Response(status_code=code)

    transport = httpx.MockTransport(fake_handler)

    service = 'test_app'
    settings = HttpServiceSettings(
        url='https://test_app.com',
        timeout=10,
        expected_status={200}
    )

    second_service = 'second_test_app'
    second_settings = HttpServiceSettings(
        url='https://second_test_app.com',
        timeout=10,
        expected_status={200}
    )

    def fake_monotonic():
        return current_time

    monkeypatch.setattr(
        http_health.time,
        "monotonic",
        fake_monotonic
    )
    services_settings = HttpServicesSettings(
        interval=60,
        failure_duration=120,
        monitored={
            service: settings,
            second_service: second_settings,
        }
    )
    async with httpx.AsyncClient(transport=transport) as client:

        result = await http_health.http_health(
            client=client,
            settings=services_settings
        )

    assert len(result) == 2

    assert result[0].service == service
    assert result[0].result_code is None
    assert result[0].is_failed is True
    assert result[0].error == 'Connection error'
    assert result[0].duration_seconds == 1

    assert result[1].service == second_service
    assert result[1].result_code == 200
    assert result[1].is_failed is False
    assert result[1].error is None
    assert result[1].duration_seconds == 2

