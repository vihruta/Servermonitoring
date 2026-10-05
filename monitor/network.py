import httpx
from config import InternetSettings
from models import HttpMetrics
from monitor import http_health



async def network_check(
        client: httpx.AsyncClient,
        service_settings: InternetSettings
) -> HttpMetrics:
    check_result = await http_health.http_service_check(
        service='Internet',
        client=client,
        service_settings=service_settings
    )

    return check_result