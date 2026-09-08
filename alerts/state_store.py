from alerts.states import State

class StateStore:
    def __init__(self):
        self.states: dict[str, State] = {}

    def get(self, metric:str) -> State:
        return self.states.get(metric, State.OK)

    def set(self, metric: str, state: State):
        self.states[metric] = state