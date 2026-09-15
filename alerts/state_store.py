import time
from alerts.states import State


class StateStore:
    def __init__(self):
        self.states: dict[str, State] = {}

    def get(self, metric:str) -> State:
        return self.states.get(metric, State.OK)

    def set(self, metric: str, state: State):
        self.states[metric] = state

class IncidentStore:
    def __init__(self):
        self.incidents: dict[str, float] = {}

    def start(self, metric: str):
        if metric not in self.incidents:
            self.incidents[metric] = time.monotonic()

    def get(self, metric: str) -> float | None:
        return self.incidents[metric]
    
    def get_downtime(self, metric: str) -> float | None:
        started_at = self.incidents.get(metric)

        if started_at is None:
            return None
        
        return time.monotonic() - self.incidents[metric]

    def remove(self, metric: str):
        self.incidents.pop(metric, None)