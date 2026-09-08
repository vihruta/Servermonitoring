from enum import Enum

class State(Enum):
    OK = 1
    WARNING = 2
    CRITICAL = 3

class Alert(Enum):
    NO_ALERT=0
    WARNING=1
    CRITICAL=2
    RECOVERED=3