from alerts.states import State, Alert
from alerts.models import MetricStatus, Thresholds

def get_current_state(
        value: float, 
        previous_state: State, 
        threshold: Thresholds
        ) -> State:
    if value < threshold.recovery:
        return State.OK
    
    elif value >= threshold.critical:
        return State.CRITICAL
    
    elif value >= threshold.warning:
        return State.WARNING
    
    else:
        if previous_state == State.CRITICAL:
            return State.WARNING
        
        return previous_state

def get_container_state(
        status: str,
        health: str | None,
        previous_state: State
        ) -> State:
    if status == 'running':
        if health == 'healthy' or health is None:
            return State.OK
        elif health == 'starting':
            return State.WARNING
        elif health == 'unhealthy':
            return State.CRITICAL
        return State.WARNING
    elif status in ("restarting", "paused", "created", "removing"):
        return State.WARNING
    elif status in ("exited", "dead", "missing"):
        return State.CRITICAL

    return previous_state


def check_alert(value: float, previous_state: State, threshold: Thresholds)-> MetricStatus:
    current_state = get_current_state(value=value, 
                                      previous_state=previous_state, 
                                      threshold=threshold)
                                      
    return check_state_transition(
        current_state=current_state,
        previous_state=previous_state)


def check_container_alert(status: str, health: str | None, previous_state: State) -> MetricStatus:
    current_state = get_container_state(
        status=status,
        health=health,
        previous_state=previous_state)

    return check_state_transition(
        current_state=current_state,
        previous_state=previous_state)


def check_state_transition(current_state: State, previous_state: State) -> MetricStatus:
    if current_state == State.OK:
        if previous_state == State.WARNING or previous_state == State.CRITICAL:
            return MetricStatus(alert=Alert.RECOVERED, state=current_state)
        
    if current_state == State.WARNING and previous_state == State.OK:
        return MetricStatus(alert=Alert.WARNING, state=current_state)

    if current_state == State.CRITICAL and previous_state != State.CRITICAL:
            return MetricStatus(alert=Alert.CRITICAL, state=current_state)

    return MetricStatus(alert=Alert.NO_ALERT, state=current_state)