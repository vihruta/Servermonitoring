import docker
import logging
from docker.models.containers import Container

from models import DockerContainerMetrics

logger = logging.getLogger(__name__)

def get_containers_health(docker_timeout: int) -> dict[str, DockerContainerMetrics | None] | None:
    client = None
    try:
        client = docker.from_env(timeout=docker_timeout)
        containers_list = client.containers.list(all=True)

        containers: dict[str, DockerContainerMetrics | None] =  {}
        for container in containers_list:
            if container.name is None:
                continue
            containers[container.name] = check_health(container)
        return containers
    except TimeoutError:
        logger.exception('Timeout while get containers')
        return None
    except Exception:
        logger.exception('Error while trying get containers')
        return None
    finally:
        if client is not None:
            client.close()


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

    