import cv2
from PIL import Image, ImageDraw, ImageFont
import math

from domain.ports.image_renderer import ImageRendererPort
from domain.models.image_spec import ImageSpecification


class OpenCVImageAdapter(ImageRendererPort):
    def __init__(self, font_path: str):
        self.font_path = font_path
        self.new_width = 1472
        self.new_height = 2624

    def _draw_text_with_border(self, draw, text, pos, font, fill, border_color, border_width):
        x, y = pos
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

    def _wrap_text(self, text, font, max_width):
        lines = []
        words = text.split()
        line = []
        for word in words:
            test_line = ' '.join(line + [word])
            bbox = font.getbbox(test_line)
            if bbox[2] - bbox[0] <= max_width:
                line.append(word)
            else:
                lines.append(' '.join(line))
                line = [word]
        if line:
            lines.append(' '.join(line))
        return lines

    def render_image(self, spec: ImageSpecification) -> str:
        color = tuple(spec.color)
        border_color = tuple(spec.border_color)
        fill_color = tuple(color)
        font_sz = 36 * 4
        border_sz = 4
        max_width = 325 * 4

        text1_pos = (50, 400)
        text2_pos = (50, text1_pos[1] + (150 * spec.text_diff_mult))

        img = cv2.imread(spec.image_path, cv2.IMREAD_UNCHANGED)
        if img is None:
            raise FileNotFoundError(f"Image at path '{spec.image_path}' not found.")

        img = cv2.resize(img, (self.new_width, self.new_height))

        pil_image = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(pil_image, 'RGBA')
        font = ImageFont.truetype(self.font_path, font_sz)

        lines1 = self._wrap_text(spec.text1, font, max_width)
        y = text1_pos[1]
        for line in lines1:
            bbox = font.getbbox(line)
            text_width = bbox[2] - bbox[0]
            line_pos = ((pil_image.width - text_width) // 2, y)
            self._draw_text_with_border(draw, line, line_pos, font, fill_color, border_color, border_sz)
            y += font_sz + border_sz * 2

        lines2 = self._wrap_text(spec.text2, font, max_width)
        y = text2_pos[1]
        for line in lines2:
            bbox = font.getbbox(line)
            text_width = bbox[2] - bbox[0]
            line_pos = ((pil_image.width - text_width) // 2, y)
            self._draw_text_with_border(draw, line, line_pos, font, fill_color, border_color, border_sz)
            y += font_sz + border_sz * 2

        pil_image.save(spec.output_path)

        return spec.output_path


def calculate_dynamic_y_shift(text1: str, font_path: str, font_sz: int, border_sz: int, max_width: int,
                              starting_y: int = 400) -> int:
    font = ImageFont.truetype(font_file=font_path, size=font_sz)

    lines = []
    words = text1.split()
    line = []
    for word in words:
        test_line = ' '.join(line + [word])
        bbox = font.getbbox(test_line)
        if bbox[2] - bbox[0] <= max_width:
            line.append(word)
        else:
            lines.append(' '.join(line))
            line = [word]
    if line:
        lines.append(' '.join(line))

    line_count = len(lines)

    line_height = font_sz + (border_sz * 2)

    padding_between_quotes = 50

    total_height_of_text1 = line_count * line_height
    new_y_position = starting_y + total_height_of_text1 + padding_between_quotes

    return new_y_position
