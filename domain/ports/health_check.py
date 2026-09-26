from abc import ABC, abstractmethod

from domain.models.health_status import HealthStatus


class HealthCheckPort(ABC):

    @abstractmethod
    def check_health(self) -> HealthStatus:
        pass
