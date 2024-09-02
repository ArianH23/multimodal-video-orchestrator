import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import json

config = json.load(open('config.json'))

CORNERS_ENUMS = {
    "TR": (1, 0),
    "BL": (0, 1),
    "TL": (0, 0),
    "BR": (1, 1),
}
def draw_text_with_border(draw, text, pos, font, fill, border_color, border_width):
    x, y = pos

    # Determine the size of the text
    (width, baseline), (offset_x, offset_y) = font.font.getsize(text)
    ascent, descent = font.getmetrics()

    # Create a mask image for the text
    text_mask = Image.new('L', (width, ascent+descent), 0)
    mask_draw = ImageDraw.Draw(text_mask)
    mask_draw.text((0, 0), text, font=font, fill=255)

    # Draw the border
    for dx in range(-border_width, border_width + 1):
        for dy in range(-border_width, border_width + 1):
            if dx != 0 or dy != 0:
                draw.bitmap((x + dx, y + dy), text_mask, fill=border_color)

    # Draw the text
    draw.bitmap((x, y), text_mask, fill=fill)


def wrap_text(text, font, max_width):
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

new_width = 1472  # Width in pixels
new_height = 2624  # Height in pixels

def overlay_text_on_image(image_path, output_image_path, title, title_pos, text1, text1_pos, text2, text2_pos, font_file,
                          title_font_sz=64, text_font_sz=32, fill=(255, 255, 255), border_color=(0, 0, 0), border_sz=2,
                          upscale_factor=1.0, max_width=None, window_size=800):
    img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)

    if img is None:
        raise FileNotFoundError(f"Image at path '{image_path}' not found.")

    if upscale_factor != 1.0:
        img = cv2.resize(img, (0, 0), fx=upscale_factor, fy=upscale_factor, interpolation=cv2.INTER_CUBIC)
    img = cv2.resize(img, (new_width, new_height))

    pil_image = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil_image, 'RGBA')
    title_font = ImageFont.truetype(font_file, title_font_sz)
    text_font = ImageFont.truetype(font_file, text_font_sz)

    if max_width:
        title_lines = wrap_text(title, title_font, max_width)
    else:
        title_lines = [title]

    y = title_pos[1]
    for line in title_lines:
        bbox = draw.textbbox((0, 0), line, font=title_font)
        text_width = bbox[2] - bbox[0]
        line_pos = ((pil_image.width - text_width) // 2, y)
        draw_text_with_border(draw, line, line_pos, title_font, fill, border_color, border_sz)
        y += title_font_sz + border_sz * 2

    if max_width:
        lines1 = wrap_text(text1, text_font, max_width)
    else:
        lines1 = [text1]

    y = text1_pos[1]
    for line in lines1:
        bbox = draw.textbbox((0, 0), line, font=text_font)
        text_width = bbox[2] - bbox[0]
        line_pos = ((pil_image.width - text_width) // 2, y)
        draw_text_with_border(draw, line, line_pos, text_font, fill, border_color, border_sz)
        y += text_font_sz + border_sz * 2

    if max_width:
        lines2 = wrap_text(text2, text_font, max_width)
    else:
        lines2 = [text2]

    y = text2_pos[1]
    for line in lines2:
        bbox = draw.textbbox((0, 0), line, font=text_font)
        text_width = bbox[2] - bbox[0]
        line_pos = ((pil_image.width - text_width) // 2, y)
        draw_text_with_border(draw, line, line_pos, text_font, fill, border_color, border_sz)
        y += text_font_sz + border_sz * 2

    pil_image.save(output_image_path)


    img_width, img_height = pil_image.size
    window_width, window_height = window_size, int(window_size*1.8)

    # Calculate aspect ratio
    aspect_ratio = min(window_width / img_width, window_height / img_height)
    new_size = (int(img_width * aspect_ratio), int(img_height * aspect_ratio))

    # Resize image for display
    resized_image = pil_image.resize(new_size)

    # Convert back to OpenCV format for display
    display_image = cv2.cvtColor(np.array(resized_image), cv2.COLOR_RGB2BGR)

    # Create and resize the display window
    cv2.namedWindow("Generated Image", cv2.WINDOW_NORMAL)
    cv2.imshow("Generated Image", display_image)
    cv2.resizeWindow("Generated Image", new_size[0], new_size[1])

    # Wait indefinitely for a key press
    cv2.waitKey(0)

    # Destroy all OpenCV windows
    cv2.destroyAllWindows()

source = config['image_source']
title_pos = None
img_suffix = None

if source == 'playground':
    title_pos = (768, 1025)
    img_suffix = '.png'

elif source == 'ideogram':
    title_pos = (768, 1025)
    img_suffix = '.jpeg'

title = config['title'].upper()
if title == 'COLLABORATION':
    title_font_sz = 72 * 2.6
    border_sz = 8

if title == 'COMPASSION':
    title_font_sz = 72 * 3.25
    border_sz = 12
elif title == 'ADAPTABILITY':
    title_font_sz = 72 * 3
    border_sz = 12
elif title == 'CONFIDENCE':
    title_font_sz = 72 * 3
    border_sz = 12
else:
    title_font_sz = 72 * 4
    border_sz =12

topics_rgb_map = {
    "strength": [139, 0, 0],
    "ingenuity": [125, 249, 255],
    "confidence": [255, 215, 0],
    "presence": [230, 230, 250],
    "purpose": [0, 100, 0],
    "positivity": [255, 255, 0],
    "compassion": [255, 182, 193],
    "adaptability": [64, 224, 208],
    "passion": [255, 69, 0],
    "discipline": [0, 0, 128],
    "collaboration": [128, 0, 128],
    "growth": [80, 200, 120],
    "curiosity": [0, 128, 128],
    "resilience": [119, 136, 153]
}

color = topics_rgb_map[config['title']]

# Example usage
overlay_text_on_image(
    '1.base_images/' + config['image_name'],
    '3.title_images/' + config['image_name'] + '.jpeg',
    title=config['title'].upper(),
    title_pos=title_pos,  # Position of the title text
    text1="",
    text1_pos=(50, 400),
    text2="",
    text2_pos=(50, 400 + config['text_y_diff'],),
    font_file='League_Spartan/static/LeagueSpartan-Bold.ttf',  # Path to the Montserrat font
    title_font_sz = title_font_sz,  # Size of the title font
    text_font_sz=36*4,  # Size of the regular text font
    fill=tuple(color),
    border_color= tuple(config['border_color']),
    border_sz=border_sz,
    upscale_factor=1.0,  # Factor to upscale the image
    max_width=375*4,  # Maximum width for text wrapping
    window_size=450
)
