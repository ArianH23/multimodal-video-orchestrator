import cv2
from PIL import Image, ImageDraw, ImageFont
import math
from domain.ports.title_renderer import TitleRendererPort
from domain.models.title_image_spec import TitleImageSpecification


class OpenCVTitleImageAdapter(TitleRendererPort):
    def __init__(self, font_path: str):
        self.font_path = font_path
        self.new_width = 1472
        self.new_height = 2624

    def _get_optimal_font_size(self, text: str, max_width: int, starting_size: int = 300) -> tuple:
        """Dynamically calculates the largest font size that fits within max_width."""
        font_sz = starting_size
        font = ImageFont.truetype(self.font_path, font_sz)

        while True:
            bbox = font.getbbox(text)
            text_width = bbox[2] - bbox[0]

            # If it fits, return the font and the size
            if text_width <= max_width or font_sz <= 10:
                return font, font_sz

            # Otherwise, shrink the font and try again
            font_sz -= 4
            font = ImageFont.truetype(self.font_path, font_sz)

    def _draw_text_with_border(self, draw, text, pos, font, fill, border_color, border_width):
        x, y = pos
        # Fixed Pillow 10 bug: getsize -> getbbox
        bbox = font.getbbox(text)
        width = bbox[2] - bbox[0]
        ascent, descent = font.getmetrics()

        text_mask = Image.new('L', (width, ascent + descent), 0)
        mask_draw = ImageDraw.Draw(text_mask)
        mask_draw.text((0, 0), text, font=font, fill=255)

        offsets = []
        for angle in range(0, 360, 45):
            dx = int(border_width * math.cos(math.radians(angle)))
            dy = int(border_width * math.sin(math.radians(angle)))
            offsets.append((dx, dy))

        for dx, dy in offsets:
            draw.bitmap((x + dx, y + dy), text_mask, fill=border_color)

        draw.bitmap((x, y), text_mask, fill=fill)

    def render_title_image(self, spec: TitleImageSpecification) -> str:
        img = cv2.imread(spec.image_path, cv2.IMREAD_UNCHANGED)
        if img is None:
            raise FileNotFoundError(f"Image at path '{spec.image_path}' not found.")

        img = cv2.resize(img, (self.new_width, self.new_height))
        pil_image = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(pil_image, 'RGBA')

        # Dynamically calculate the font!
        # We allow a max width of 1300px so it doesn't touch the very edges of the 1472px image
        title_font, final_font_sz = self._get_optimal_font_size(
            text=spec.title_text,
            max_width=1300,
            starting_size=288  # 72 * 4
        )

        # Scale border dynamically based on how small the font got
        border_sz = max(4, int(final_font_sz * 0.04))

        # Calculate centering
        bbox = title_font.getbbox(spec.title_text)
        text_width = bbox[2] - bbox[0]
        x_pos = (self.new_width - text_width) // 2
        y_pos = 1025  # From your original script

        self._draw_text_with_border(
            draw=draw,
            text=spec.title_text,
            pos=(x_pos, y_pos),
            font=title_font,
            fill=spec.color,
            border_color=spec.border_color,
            border_width=border_sz
        )

        pil_image.save(spec.output_path)

        # cv2.imshow and waitKey have been strictly removed
        return spec.output_path