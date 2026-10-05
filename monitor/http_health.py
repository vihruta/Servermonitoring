import httpx
import asyncio
import logging
import time

from models import HttpMetrics
from config import HttpServicesSettings, HttpServiceSettings

logger = logging.getLogger(__name__)

async def http_health(
        client: httpx.AsyncClient,
        settings: HttpServicesSettings  
) -> list[HttpMetrics]:
    http_health_list : list[HttpMetrics] = []
    for service, service_settings in settings.monitored.items():
        try:
            service_status = await http_service_check(
                service=service,
                client=client,
                service_settings=service_settings
            )
        except Exception:
            logger.exception('HTTP check failed | APP %s', service)
            continue
        http_health_list.append(service_status)

    return http_health_list


async def http_service_check(
        service: str,
        client: httpx.AsyncClient,
        service_settings: HttpServiceSettings
) -> HttpMetrics:
    try:
        started_at = time.monotonic()
        result = await client.get(
            service_settings.url,
            timeout=service_settings.timeout)
        result_time = time.monotonic() - started_at

        if result.status_code in service_settings.expected_status:
            is_failed = False
            error = None
        else:
            is_failed = True
            error = 'Unexpected HTTP status'

        return HttpMetrics(
            service=service,
            result_code=result.status_code,
            is_failed=is_failed,
            error=error,
            duration_seconds=result_time
        )

    except httpx.ConnectError as exc:
        result_time = time.monotonic() - started_at
        logger.exception(
            'Connection error | APP %s | %s',
            service,exc
            )
        
        return HttpMetrics(
            service=service,
            result_code=None,
            is_failed=True,
            error='Connection error',
            duration_seconds=result_time
        )
    
    except httpx.TimeoutException as exc:
        result_time = time.monotonic() - started_at
        logger.exception(
            'Timeout error(HTTP) | APP %s | %s',
            service,
            exc
        )

        return HttpMetrics(
            service=service,
            result_code=None,
            is_failed=True,
            error='Timeout error',
            duration_seconds=result_time
        )

    except httpx.RequestError as exc:
        logger.exception('HTTP request error | APP %s | %s', service, exc)
        return HttpMetrics(
            service=service,
            result_code=None,
            is_failed=True,
            error='Request error',
            duration_seconds=time.monotonic() - started_at
        )
