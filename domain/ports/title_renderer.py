from abc import ABC, abstractmethod
from domain.models.title_image_spec import TitleImageSpecification

class TitleRendererPort(ABC):
    @abstractmethod
    def render_title_image(self, spec: TitleImageSpecification) -> str:
        pass
