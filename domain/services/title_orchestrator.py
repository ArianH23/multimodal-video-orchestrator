import os
from domain.ports.title_renderer import TitleRendererPort
from domain.ports.storage import StoragePort
from domain.models.title_image_spec import TitleImageSpecification


class TitleImageOrchestratorService:
    def __init__(self, renderer: TitleRendererPort, storage: StoragePort):
        self.renderer = renderer
        self.storage = storage

    def _clean_text(self, text: str) -> str:
        """Domain logic to sanitize character encoding issues."""
        replacements = {
            'Ã¡': 'á', 'Ã©': 'é', 'Ã\xad': 'í',
            'Ã³': 'ó', 'Ãº': 'ú'
        }
        for k, v in replacements.items():
            text = text.replace(k, v)
        return text

    def generate_title(self, title: str, input_image_path: str, color: list, border_color: list) -> str:
        print(f"Orchestrating title image for: {title}")

        clean_title = self._clean_text(title.upper())

        base_filename = os.path.splitext(os.path.basename(input_image_path))[0]

        temp_image_path = f"temp_title_{base_filename}.png"

        spec = TitleImageSpecification(
            image_path=input_image_path,
            output_path=temp_image_path,
            topic=title,
            title_text=clean_title,
            color=tuple(color),
            border_color=tuple(border_color)
        )

        rendered_temp_path = self.renderer.render_title_image(spec)

        final_destination = f"data/title_images/{base_filename}.png"
        final_image_path = self.storage.move(rendered_temp_path, final_destination)

        print(f"Title image successfully rendered to {final_image_path}")
        return final_image_path
