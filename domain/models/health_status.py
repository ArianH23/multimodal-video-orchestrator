from dataclasses import dataclass


@dataclass
class HealthStatus:
    status: str  # "OK", "WARN", "FAIL", or "SKIPPED"
    detail: str
