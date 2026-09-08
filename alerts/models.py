from pydantic import BaseModel
from alerts.states import State, Alert

class MetricStatus(BaseModel):
    alert: Alert
    state: State