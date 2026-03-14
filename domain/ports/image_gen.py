from abc import ABC, abstractmethod


class ImageGeneratorPort(ABC):

    @abstractmethod
    def create_image(self, prompt: str):
        pass
