# domain/services/image_overlay_orchestrator.py
from domain.ports.image_renderer import ImageRendererPort
from domain.ports.storage import StoragePort
from domain.models.image_spec import ImageSpecification


class ImageOverlayOrchestratorService:
    def __init__(self, renderer: ImageRendererPort, storage: StoragePort):
        self.renderer = renderer
        self.storage = storage

    def _clean_text(self, text: str) -> str:
        """Domain logic to sanitize character encoding issues."""
        replacements = {
            'Ã¡': 'á', 'Ã©': 'é', 'Ã\xad': 'í',
            'Ã³': 'ó', 'Ãº': 'ú', 'Â¿': '¿', 'Ã±': 'ñ'
        }
        for k, v in replacements.items():
            text = text.replace(k, v)
        return text

    def generate_final_image(self, title: str, quotes: dict, input_image_path: str,
                             color: list, suggested_border_rgb: list, text_diff_mult: int) -> str:
        print(f"Orchestrating text overlay for {title}...")

        clean_text1 = self._clean_text(quotes["text1"])
        clean_text2 = self._clean_text(quotes["text2"])

        temp_image_path = f"temp_render_{title}.png"

        spec = ImageSpecification(
            image_path=input_image_path,
            output_path=temp_image_path,
            topic=title,
            text1=clean_text1,
            text2=clean_text2,
            text_diff_mult=text_diff_mult,
            color=color,
            border_color=suggested_border_rgb
        )

        rendered_temp_path = self.renderer.render_image(spec)

        final_destination = f"data/final_images/{title}.png"
        final_image_path = self.storage.move(rendered_temp_path, final_destination)

        print(f"Image successfully overlaid and saved to {final_image_path}")
        return final_image_path
