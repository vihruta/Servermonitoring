import pytest

from alerts.states import State, Alert
from alerts.models import Thresholds
from alerts.manager import (get_current_state, check_state_transition,
                            get_container_state, check_container_alert,
                            get_http_state)

@pytest.mark.parametrize(
    "value, previous_state, expected_state",
    [
        (74.9, State.WARNING, State.OK),
        (75, State.OK, State.OK),
        (75, State.WARNING, State.WARNING),

        (84.9, State.WARNING, State.WARNING),
        (85, State.OK, State.WARNING),

        (94.9, State.OK, State.WARNING),
        (95, State.OK, State.CRITICAL),
    ]
)

def test_get_current_state(
    value,
    previous_state,
    expected_state
):
    thresholds = Thresholds(
        warning=85,
        critical=95,
        recovery=75
    )

    result = get_current_state(
        value=value,
        previous_state=previous_state,
        threshold=thresholds
        )

    assert result == expected_state

@pytest.mark.parametrize(
    "previous_state, current_state, expected_alert", 
    [
        (State.OK, State.OK, Alert.NO_ALERT),
        (State.OK, State.WARNING, Alert.WARNING),
        (State.OK, State.CRITICAL, Alert.CRITICAL),
        (State.WARNING, State.OK, Alert.RECOVERED),
        (State.WARNING, State.WARNING, Alert.NO_ALERT),
        (State.WARNING, State.CRITICAL, Alert.CRITICAL),
        (State.CRITICAL, State.OK, Alert.RECOVERED),
        (State.CRITICAL, State.WARNING, Alert.NO_ALERT),
        (State.CRITICAL, State.CRITICAL, Alert.NO_ALERT)
    ]
)

def test_check_state_transition(
    previous_state, current_state, expected_alert
):
    result = check_state_transition(
        current_state=current_state,
        previous_state=previous_state)

    assert result.alert == expected_alert
    assert result.state == current_state

@pytest.mark.parametrize(
        "status, health, current_state",
        [
            ('running', 'healthy', State.OK),
            ('running', None, State.OK),
            ('running', 'starting', State.WARNING),
            ('running', 'unhealthy', State.CRITICAL),
            ('restarting', None, State.WARNING),
            ('exited', None, State.CRITICAL),
            ('dead', None, State.CRITICAL),
            ('missing', None, State.CRITICAL)
        ]
)

def test_get_container_state(
    status,
    health,
    current_state
):
    result = get_container_state(
        status=status,
        health=health,
        previous_state=State.OK
    )

    assert result == current_state


@pytest.mark.parametrize(
        'previous_state, status, expected_alert',
        [
            (State.OK, 'running', Alert.NO_ALERT),
            (State.OK, 'exited', Alert.CRITICAL),
            (State.CRITICAL, 'exited', Alert.NO_ALERT),
            (State.CRITICAL,'running', Alert.RECOVERED)
        ]
)
def test_monitoring_containers_state_transition(
    previous_state,
    status,
    expected_alert
):
    result = check_container_alert(
        status=status,
        health=None,
        previous_state=previous_state
    )

    assert result.alert == expected_alert


@pytest.mark.parametrize(
    "result_code, is_failed, expected_state",
    [
        (200, False, State.OK),
        (503, True, State.WARNING),
        (None, True, State.CRITICAL),
    ],
)
def test_get_http_state(result_code, is_failed, expected_state):
    result = get_http_state(
        result_code=result_code,
        is_failed=is_failed,
    )

    assert result == expected_state