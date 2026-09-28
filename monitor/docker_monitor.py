import docker
import logging
from docker.models.containers import Container

from models import DockerContainerMetrics

logger = logging.getLogger(__name__)

def get_containers_health() -> dict[str, DockerContainerMetrics | None] | None:
    try:
        client = docker.from_env()
        containers_list = client.containers.list(all=True)

        containers: dict[str, DockerContainerMetrics | None] =  {}
        for container in containers_list:
            if container.name is None:
                continue
            containers[container.name] = check_health(container)
        return containers
    except Exception:
        logger.exception('Error while trying get containers')
        return None


def check_health(container: Container) ->  DockerContainerMetrics | None:
    try:
        state = container.attrs['State']
        
        health_data = state.get('Health')
        health = health_data.get('Status') if health_data is not None else None

        return DockerContainerMetrics(
            status=container.status,
            oom_killed=state.get('OOMKilled'),
            exit_code=state.get('ExitCode'),
            error=state.get('Error'),
            health=health
            )
    except Exception:
        logger.exception('Get container info error | Container %s',
                         container.name)
        return None

    