from pydantic import BaseModel
from alerts.states import State, Alert

class MetricStatus(BaseModel):
    alert: Alert
    state: State

class Thresholds(BaseModel):
    warning: float
    critical: float
    recovery: float

class NumericAlertData(BaseModel):
    status: MetricStatus
    value: float
    unit: str

class ContainerAlertData(BaseModel):
    status: MetricStatus
    container_status: str
    container_health: str | None
    downtime: float | None
