from abc import ABC, abstractmethod
from domain.models.image_spec import ImageSpecification


class ImageRendererPort(ABC):
    @abstractmethod
    def render_image(self, spec: ImageSpecification) -> str:
        """Renders the text overlay on the image and returns the saved file path."""
        pass
