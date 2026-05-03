from abc import ABC, abstractmethod
from typing import List
from domain.models.trends import MotivationalTopic


class TopicRepositoryPort(ABC):
    @abstractmethod
    def find_similar_topics(self, query: str, limit: int) -> List[MotivationalTopic]:
        pass

    @abstractmethod
    def get_random_topics(self, limit: int) -> List[MotivationalTopic]:
        pass
