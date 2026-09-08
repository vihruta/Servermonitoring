import docker
from docker.models.containers import Container

from models import DockerContainerMetrics

def get_containers_health() -> dict[str, DockerContainerMetrics]:
    client = docker.from_env()
    containers_list = client.containers.list(all=True)

    containers: dict[str, DockerContainerMetrics] =  {}
    for container in containers_list:
        if container.name is None:
            continue
        containers[container.name] = check_health(container)
    return containers


def check_health(container: Container) ->  DockerContainerMetrics:
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

    