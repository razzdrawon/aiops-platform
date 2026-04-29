from enum import Enum


class IncidentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    RESOLVED = "resolved"
    BLOCKED = "blocked"      # guardrail stopped the action
    FAILED = "failed"        # pipeline error


class ActionType(str, Enum):
    ROLLBACK = "rollback"
    RESTART_SERVICE = "restart_service"
    SCALE_UP = "scale_up"
    CREATE_PR_FIX = "create_pr_fix"
    NOOP = "noop"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentClass(str, Enum):
    OOM = "oom"
    DEPLOY_FAILURE = "deploy_failure"
    DB_OVERLOAD = "db_overload"
    HIGH_ERROR_RATE = "high_error_rate"
    LATENCY_SPIKE = "latency_spike"
    UNKNOWN = "unknown"
