from pydantic import BaseModel, Field
from alerts.states import State, Alert

class MetricStatus(BaseModel):
    alert: Alert
    state: State

class Thresholds(BaseModel):
    warning: float
    critical: float
    recovery: float
    warning_duration: float = Field(default=0, ge=0)
    cooldown: float = Field(default=300, ge=0)

class NumericAlertData(BaseModel):
    status: MetricStatus
    value: float
    unit: str

class ContainerAlertData(BaseModel):
    status: MetricStatus
    container_status: str
    container_health: str | None
    downtime: float | None