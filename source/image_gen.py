import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import json

new_width = 1472  # Width in pixels
new_height = 2624  # Height in pixels

def clean_texts(quotes):
    quotes['text1'] = quotes['text1'].replace('Ã¡', 'á')
    quotes['text1'] = quotes['text1'].replace('Ã©', 'é')
    quotes['text1'] = quotes['text1'].replace('Ã\xad', 'í')
    quotes['text1'] = quotes['text1'].replace('Ã³', 'ó')
    quotes['text1'] = quotes['text1'].replace('Ãº', 'ú')
    quotes['text1'] = quotes['text1'].replace('Â¿', '¿')
    quotes['text1'] = quotes['text1'].replace('Ã±', 'ñ')

    quotes['text2'] = quotes['text2'].replace('Ã¡', 'á')
    quotes['text2'] = quotes['text2'].replace('Ã©', 'é')
    quotes['text2'] = quotes['text2'].replace('Ã\xad', 'í')
    quotes['text2'] = quotes['text2'].replace('Ã³', 'ó')
    quotes['text2'] = quotes['text2'].replace('Ãº', 'ú')
    quotes['text2'] = quotes['text2'].replace('Ã±', 'ñ')


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


def overlay_text_on_image(image_path, output_image_path, text1, text1_pos, text2, text2_pos, font_file, font_sz=32,
                          fill=(255, 255, 255), border_color=(0, 0, 0), border_sz=2, upscale_factor=1.0,
                          max_width=None, window_size=800):
    img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
    img = cv2.resize(img, (new_width, new_height))

    if img is None:
        raise FileNotFoundError(f"Image at path '{image_path}' not found.")

    if upscale_factor != 1.0:
        img = cv2.resize(img, (0, 0), fx=upscale_factor, fy=upscale_factor, interpolation=cv2.INTER_CUBIC)

    pil_image = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil_image, 'RGBA')
    font = ImageFont.truetype(font_file, font_sz)

    if max_width:
        lines1 = wrap_text(text1, font, max_width)
    else:
        lines1 = [text1]

    y = text1_pos[1]
    for line in lines1:
        bbox = font.getbbox(line)
        text_width = bbox[2] - bbox[0]
        line_pos = ((pil_image.width - text_width) // 2, y)
        draw_text_with_border(draw, line, line_pos, font, fill, border_color, border_sz)
        y += font_sz + border_sz * 2

    if max_width:
        lines2 = wrap_text(text2, font, max_width)
    else:
        lines2 = [text2]

    y = text2_pos[1]
    for line in lines2:
        bbox = font.getbbox(line)
        text_width = bbox[2] - bbox[0]
        line_pos = ((pil_image.width - text_width) // 2, y)
        draw_text_with_border(draw, line, line_pos, font, fill, border_color, border_sz)
        y += font_sz + border_sz * 2

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


def generate_image(suggested_border_rgb, topic, quotes, image_name, text_diff_mult):

    clean_texts(quotes)
    text1_pos = (50, 400)

    topics_rgb_map = json.load(open('topics.json'))
    color = topics_rgb_map[topic.lower()]

    text2_y_pos = text1_pos[1] + (150 * text_diff_mult)

    # Example usage
    overlay_text_on_image(
        '1.base_images/' + image_name,
        '2.sample_images/' + image_name.split('.')[0] + '.jpeg',
        text1=quotes['text1'],
        text1_pos=text1_pos,
        text2=quotes['text2'],
        text2_pos=(50, text2_y_pos,),
        font_file='League_Spartan/static/LeagueSpartan-Bold.ttf',
        font_sz=36*4,  # Size of the font
        fill=tuple(color),
        border_color=tuple(suggested_border_rgb),
        border_sz=4,
        upscale_factor=1.0,  # Factor to upscale the image
        max_width=325*4,  # Maximum width for text wrapping
        window_size=450
    )
