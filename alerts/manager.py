from alerts.states import State, Alert
from alerts.models import MetricStatus

def get_cpu_temp_state(temperature: float, previous_state: State) -> State:
    if temperature < 80:
        return State.OK
    elif temperature >= 95:
        return State.CRITICAL
    elif temperature >= 90:
        return State.WARNING
    else:
        if previous_state == State.OK or previous_state == State.WARNING:
            return previous_state
        return State.WARNING

def check_alert(temperature: float, previous_state: State)-> MetricStatus:
    current_state = get_cpu_temp_state(temperature=temperature, previous_state=previous_state)
    if current_state == State.OK:
        if previous_state == State.WARNING or previous_state == State.CRITICAL:

            return MetricStatus(alert=Alert.RECOVERED, state=current_state)
        
    if current_state == State.WARNING and previous_state == State.OK:
        return MetricStatus(alert=Alert.WARNING, state=current_state)
    
    if current_state == State.CRITICAL:
        if previous_state == State.OK or previous_state == State.WARNING:
            return MetricStatus(alert=Alert.CRITICAL, state=current_state)
    return MetricStatus(alert=Alert.NO_ALERT, state=current_state)