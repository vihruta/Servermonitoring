from datetime import datetime, timedelta, timezone

from alerts.state_store import HttpSnapshotStore, SmartSnapshotStore
from models import HttpMetrics, SmartMetrics


def test_http_snapshot_keeps_last_success_after_failure():
    store = HttpSnapshotStore()
    started = datetime(2026, 10, 13, tzinfo=timezone.utc)
    failed = HttpMetrics(service='app', result_code=None, is_failed=True,
                         error='Timeout error', duration_seconds=10)
    success = HttpMetrics(service='app', result_code=200, is_failed=False,
                          error=None, duration_seconds=0.1)

    assert store.get('app') is None
    store.update('app', failed, started)
    assert store.get('app').last_success_at is None

    success_at = started + timedelta(seconds=60)
    store.update('app', success, success_at)
    assert store.get('app').last_success_at == success_at

    failure_at = started + timedelta(seconds=120)
    store.update('app', failed, failure_at)
    snapshot = store.get('app')
    assert snapshot.metrics == failed
    assert snapshot.checked_at == failure_at
    assert snapshot.last_success_at == success_at

    # У другого сервиса не должно появляться чужое время успеха.
    store.update('other', failed.model_copy(update={'service': 'other'}), failure_at)
    assert store.get('other').last_success_at is None
    assert store.get('app') == snapshot

    recovery_at = started + timedelta(seconds=180)
    store.update('app', success, recovery_at)
    assert store.get('app').last_success_at == recovery_at


def test_smart_failed_check_replaces_old_snapshot():
    store = SmartSnapshotStore()
    checked_at = datetime(2026, 10, 13, tzinfo=timezone.utc)
    metrics = SmartMetrics(critical_warning=0, available_spare=100,
                           percent_used=2, media_errors=0, num_err_log_entries=0)
    store.update('/dev/nvme0n1', metrics, checked_at)
    assert store.get('/dev/nvme0n1').metrics == metrics

    failed_at = checked_at + timedelta(hours=1)
    store.update('/dev/nvme0n1', None, failed_at)
    assert store.get('/dev/nvme0n1').metrics is None
    assert store.get('/dev/nvme0n1').checked_at == failed_at
