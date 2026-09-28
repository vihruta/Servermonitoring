import time
from alerts.states import State


class StateStore:
    def __init__(self):
        self.states: dict[str, State] = {}

    def get(self, metric:str) -> State:
        return self.states.get(metric, State.OK)

    def set(self, metric: str, state: State):
        self.states[metric] = state

class PendingStore:
    def __init__(self):
        self.pending_time: dict[str, dict[State, float]] = {}

    def start(self, metric: str, state: State):
        if metric not in self.pending_time:
            self.pending_time[metric] = {state: time.monotonic()}

    def get(self, metric: str, state: State) -> float | None:
        if self.pending_time.get(metric) is not None and self.pending_time[metric].get(state) is not None:
            return time.monotonic() - self.pending_time[metric][state]
        else: 
            return None

    def remove(self, metric: str) -> None:
        self.pending_time.pop(metric, None)


class IncidentStore:
    def __init__(self):
        self.incidents: dict[str, float] = {}

    def start(self, metric: str):
        if metric not in self.incidents:
            self.incidents[metric] = time.monotonic()

    def get(self, metric: str) -> float | None:
        return self.incidents.get(metric)
    
    def get_downtime(self, metric: str) -> float | None:
        started_at = self.incidents.get(metric)

        if started_at is None:
            return None
        
        return time.monotonic() - self.incidents[metric]

    def remove(self, metric: str):
        self.incidents.pop(metric, None)

class AlertCooldownStore():
    def __init__(self):
        self.cooldown: dict[str, float] = {}

    def start(self, metric: str):
        self.cooldown[metric] = time.monotonic()

    def check(self, metric: str, metric_cooldown: float) -> bool:
        last_sent_at = self.cooldown.get(metric)

        if last_sent_at is None:
            return True

        elapsed = time.monotonic() - last_sent_at
        return elapsed >= metric_cooldown


    def remove(self, metric: str):
        self.cooldown.pop(metric, None)

    