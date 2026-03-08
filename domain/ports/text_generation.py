from abc import ABC, abstractmethod

import PIL.PngImagePlugin


class TextGenerationPort(ABC):

    @abstractmethod
    def generate_script_json(self, prompt: str) -> dict:
        pass

    @abstractmethod
    def generate_content_through_image(self, image: PIL.PngImagePlugin.PngImageFile, prompt: str) -> str:
        pass
