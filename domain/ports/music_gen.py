from abc import ABC, abstractmethod


class MusicGeneratorPort(ABC):

    @abstractmethod
    def create_music(self, prompt: str) -> bytes:
        pass

    @abstractmethod
    def get_music(self, path: str):
        pass
