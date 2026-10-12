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


class SmartAlertReason(Enum):
    CRITICAL_WARNING = 'critical_warning'
    LOW_SPARE = 'low_spare'
    HIGH_WEAR = 'high_wear'
    MEDIA_ERRORS_INCREASED = 'media_errors_increased'
    ERROR_LOG_INCREASED = 'error_log_increased'