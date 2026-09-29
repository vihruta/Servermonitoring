import subprocess
from time import sleep

from monitor import system, docker_monitor
from config import Settings, get_yaml_config

def test_get_disk_temp_timeout_error(monkeypatch):

    def mock_run(*args, **kwagrs):
        raise subprocess.TimeoutExpired(
            cmd=[0],
            timeout=kwagrs["timeout"]
        )
    
    monkeypatch.setattr(system.subprocess, 'run', mock_run)

    temp = system.get_disk_temp('abc', smartctl_timeout=10)

    assert temp == None


def test_get_disk_temp_happypath(monkeypatch):

    class MockResult:
        stdout = '{"temperature": {"current": 50.0}}'
        returncode = 0

    def mock_run(*args, **kwagrs):
        return MockResult()

    monkeypatch.setattr(system.subprocess, 'run', mock_run)

    temp = system.get_disk_temp('abc', smartctl_timeout=10)

    assert temp == 50.0



def test_get_parent_block_happypath(monkeypatch):

    def mock_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stderr=None,
            stdout='abc\n'
        )
    monkeypatch.setattr(system.subprocess,'run', mock_run)

    parent = system.get_parent_block('abc2', lsblk_timeout=10)

    assert parent == '/dev/abc'


def test_get_parent_block_error(monkeypatch):

    def mock_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=1,
            stderr='error',
            stdout='sdc'
        )
    monkeypatch.setattr(system.subprocess,'run', mock_run)

    parent = system.get_parent_block('sdc1', lsblk_timeout=10)

    assert parent is None

def test_get_parent_block_timeout(monkeypatch):

    def mock_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(
            cmd=args[0],
            timeout=kwargs["timeout"]
    )

    monkeypatch.setattr(system.subprocess, 'run', mock_run)

    parent = system.get_parent_block('sdc', lsblk_timeout=10)

    assert parent is None


def test_get_parent_block_empty_parent(monkeypatch):

    def mock_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stderr=None,
            stdout=''
        )
    
    monkeypatch.setattr(system.subprocess,'run', mock_run)

    parent = system.get_parent_block('abc2', lsblk_timeout=10)

    assert parent is None


def test_get_parent_block_command_not_found(monkeypatch):

    def mock_run(*args, **kwargs):
        raise FileNotFoundError()

    monkeypatch.setattr(system.subprocess, 'run', mock_run)

    parent = system.get_parent_block('sdc',  lsblk_timeout=10)

    assert parent is None

def test_docker_client_closing(monkeypatch):

    class FakeContainers:
        def list(self, all=True):
            return []
        
    class FakeClient:

        def __init__(self):
            self.closed = False
            self.containers = FakeContainers()

        def close(self):
            self.closed = True

    client = FakeClient()

    def fake_from_env(*args,**kwargs):
        return client
    
    monkeypatch.setattr(docker_monitor.docker,
                        'from_env',
                        fake_from_env)

    result = docker_monitor.get_containers_health(docker_timeout=10)

    assert client.closed
    assert result == {}



def test_docker_client_list_error(monkeypatch):

    class FakeContainers:
        def list(self, all=True):
            raise RuntimeError('Error')
        
    class FakeClient:

        def __init__(self):
            self.closed = False
            self.containers = FakeContainers()

        def close(self):
            self.closed = True

    client = FakeClient()

    def fake_from_env(*args,**kwargs):
        return client
    
    monkeypatch.setattr(docker_monitor.docker,
                        'from_env',
                        fake_from_env)

    result = docker_monitor.get_containers_health(docker_timeout=10)

    assert client.closed
    assert result is None

