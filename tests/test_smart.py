from monitor import smart
import subprocess
import json
import pytest

from models import SmartMetrics

def test_disk_smart_returns_metrics(monkeypatch):

    data = {
        'critical_warning': 0,
        'temperature': 300,
        'available_spare': 100,
        'percent_used': 2,
        'media_errors': 0,
        'num_err_log_entries': 0,
    }

    def mock_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stderr=None,
            stdout=json.dumps(data)
        )

    monkeypatch.setattr(
        smart.subprocess,
        'run',
        mock_run
    )

    result = smart.get_disk_smart(
        disk='/dev/nvme0',
        smartlog_timeout=10
    )
    
    assert result is not None
    assert result.model_dump() == {key: value for key, value in data.items()
                                   if key != "temperature"}


def test_disk_smart_return_broken_json(monkeypatch):

    def mock_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stderr=None,
            stdout='{broken json'
        )

    monkeypatch.setattr(
        smart.subprocess,
        'run',
        mock_run
    )


    result = smart.get_disk_smart(
        disk='/dev/nvme0',
        smartlog_timeout=10
    )

    assert result is None


def test_nvme_smartlog_continues_after_disk_failure(monkeypatch):

    calling = 0
    disk1, disk2 = '/dev/nvme0', '/dev/nvme1'

    def fake_get_disk_list(smartlog_timeout: float) -> list[str]:
        return [disk1, disk2]

    monkeypatch.setattr(
        smart,
        'get_disk_list',
        fake_get_disk_list
    )

    def fake_get_disk_smart(
            disk: str,
            smartlog_timeout: float
    ):
        nonlocal calling

        calling += 1

        if disk == disk1:
            return None

        return SmartMetrics(
            critical_warning=0,
            temperature=0,
            available_spare=0,
            percent_used=0,
            media_errors=0,
            num_err_log_entries=0
        )

    monkeypatch.setattr(
        smart,
        'get_disk_smart',
        fake_get_disk_smart
    )

    result = smart.get_nvme_smartlog(smartlog_timeout=10)

    assert result is not None
    assert result[disk1] is None
    assert isinstance(result[disk2], SmartMetrics)
    assert calling == 2
    assert set(result) == {disk1, disk2}

@pytest.mark.parametrize('payload, expected', [
    ({'Devices': [{'DevicePath': '/dev/nvme0n1'}, {'DevicePath': '/dev/nvme1n1'}]},
     ['/dev/nvme0n1', '/dev/nvme1n1']),
    ({'Devices': []}, []),
    ({'Devices': [{}]}, None),
    ({}, None),
])
def test_disk_discovery(monkeypatch, payload, expected):
    def mock_run(args, **kwargs):
        assert args == ['sudo', '-n', 'nvme', 'list', '-o', 'json']
        assert kwargs['timeout'] == 7
        return subprocess.CompletedProcess(args, 0, stdout=json.dumps(payload))

    monkeypatch.setattr(smart.subprocess, 'run', mock_run)
    assert smart.get_disk_list(7) == expected


@pytest.mark.parametrize('error', ['timeout', 'exit', 'missing_command'])
@pytest.mark.parametrize('operation', ['list', 'smart'])
def test_nvme_command_errors_return_none(monkeypatch, error, operation):
    def mock_run(args, **kwargs):
        assert kwargs['timeout'] == 7
        if error == 'timeout':
            raise subprocess.TimeoutExpired(args, kwargs['timeout'])
        if error == 'missing_command':
            raise FileNotFoundError('sudo not found')
        return subprocess.CompletedProcess(args, 1, stdout='', stderr='Permission denied')

    monkeypatch.setattr(smart.subprocess, 'run', mock_run)
    result = (smart.get_disk_list(7) if operation == 'list'
              else smart.get_disk_smart('/dev/nvme0n1', 7))
    assert result is None


@pytest.mark.parametrize('payload', [{}, [], {
    'critical_warning': 'invalid', 'available_spare': 100, 'percent_used': 2,
    'media_errors': 0, 'num_err_log_entries': 0,
}])
def test_smart_invalid_data_returns_none(monkeypatch, payload):
    def mock_run(args, **kwargs):
        return subprocess.CompletedProcess(args, 0, stdout=json.dumps(payload))

    monkeypatch.setattr(smart.subprocess, 'run', mock_run)
    assert smart.get_disk_smart('/dev/nvme0n1', 7) is None


@pytest.mark.parametrize('disks, expected', [(None, None), ([], {})])
def test_nvme_collection_distinguishes_failure_from_no_devices(monkeypatch, disks, expected):
    monkeypatch.setattr(smart, 'get_disk_list', lambda **kwargs: disks)
    assert smart.get_nvme_smartlog(7) == expected
