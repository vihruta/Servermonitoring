import docker

def get_containers_health():
    client = docker.from_env()
    containers_list = client.containers.list(all=True)
    containers = {}
    for container in containers_list:
        containers.update(check_health(container))
    return containers


def check_health(container):
    name = container.name
    status = container.status
    state = container.attrs['State']
    oom_killed = state.get('OOMKilled')
    exit_code = state.get('ExitCode')
    error = state.get('Error')
    health_data = state.get('Health')
    health = health_data.get('Status') if health_data is not None else None

    return {
        name: {
            'status': status,
            'oom_killed' : oom_killed,
            'exit_code' : exit_code,
            'error' : error,
            'health': health 
        }
    }

    