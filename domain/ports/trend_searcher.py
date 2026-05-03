from abc import ABC, abstractmethod
from domain.models.trends import TrendReport


class TrendSearcherPort(ABC):
    @abstractmethod
    def fetch_current_trends(self, region: str) -> TrendReport:
        """Fetches a synthesized summary of today's motivational trends."""
        pass
