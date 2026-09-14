from pydantic import BaseModel
from alerts.states import State, Alert

class MetricStatus(BaseModel):
    alert: Alert
    state: State

class Thresholds(BaseModel):
    warning: float
    critical: float
    recovery: float

class AlertData(BaseModel):
    status: MetricStatus
    value: float
    unit: str