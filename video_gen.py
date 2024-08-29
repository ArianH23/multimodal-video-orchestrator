import time
import json
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import VideoFileClip, AudioFileClip
import textwrap

config = json.load(open('config.json'))

CORNERS_ENUMS ={
    "TR": (1, 0),
    "BL": (0, 1),
    "TL": (0, 0),
    "BR": (1, 1),
}

def enhance_image(img):
    gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    lab_img = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab_img)
    clahe_filter = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    cl_channel = clahe_filter.apply(l_channel)
    merged_img = cv2.merge((cl_channel, a_channel, b_channel))
    contrast_img = cv2.cvtColor(merged_img, cv2.COLOR_LAB2BGR)
    rows, cols = img.shape[:2]
    x_kernel = cv2.getGaussianKernel(cols, 200)
    y_kernel = cv2.getGaussianKernel(rows, 200)
    kernel = y_kernel * x_kernel.T
    mask = 255 * kernel / np.linalg.norm(kernel)
    mask = mask.astype(np.uint8)
    vignette_img = np.copy(contrast_img)
    for i in range(3):
        vignette_img[:, :, i] = vignette_img[:, :, i] * mask
    final_img = cv2.addWeighted(contrast_img, 0.7, vignette_img.astype(np.uint8), 0.3, 0)
    return final_img


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


def overlay_text_on_frame(frame, text, pos, font_file, font_sz=32, color=(255, 255, 255), border_color=(0, 0, 0),
                          border_sz=2, alpha=1.0, max_width=None):
    pil_image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    text_layer = Image.new('RGBA', pil_image.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(text_layer)
    font = ImageFont.truetype(font_file, font_sz)

    if max_width:
        lines = wrap_text(text, font, max_width)
    else:
        lines = [text]

    y = pos[1]
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        text_width = bbox[2] - bbox[0]
        line_pos = ((pil_image.width - text_width) // 2, y)
        draw_text_with_border(draw, line, line_pos, font, color, border_color, border_sz)
        y += font_sz + border_sz * 2

    text_layer_np = np.array(text_layer)
    text_layer_np[..., 3] = (text_layer_np[..., 3] * alpha).astype(np.uint8)
    text_layer = Image.fromarray(text_layer_np)
    pil_image = Image.alpha_composite(pil_image.convert('RGBA'), text_layer)
    return cv2.cvtColor(np.array(pil_image.convert('RGB')), cv2.COLOR_RGB2BGR)

new_width = 1472  # Width in pixels
new_height = 2624  # Height in pixels

def create_ken_burns_video(input_img, output_vid, duration=10, fps=30, start_zoom=1.0, end_zoom=2.0, start_pt=(0, 0),
                           end_pt=(1, 1), use_effect=False, text1=None, text1_pos=(50, 50), text2=None,
                           text2_pos=(50, 100), font_file='Montserrat-Regular.ttf', font_sz=32, color=(255, 255, 255),
                           border_color=(0, 0, 0), border_sz=2, audio_file=None, max_width=None, upscale_factor=1.0, epic_part_of_audio=6):
    img = cv2.imread(input_img, cv2.IMREAD_UNCHANGED)
    img = cv2.resize(img, (new_width, new_height))

    if use_effect:
        img = enhance_image(img)

    h, w, _ = img.shape
    total_frames = duration * fps
    start_fade_frame = 6 * fps
    end_fade_frame = start_fade_frame + 2 * fps
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    video_writer = cv2.VideoWriter('temp_video.mp4', fourcc, fps, (w, h))

    for frame_num in range(total_frames):
        if frame_num % 10 ==0:
            print(frame_num,'/', total_frames)
        progress = frame_num / total_frames
        zoom = start_zoom + (end_zoom - start_zoom) * progress
        new_w = int(w * zoom)
        new_h = int(h * zoom)

        resized_img = cv2.resize(img, (new_w, new_h))
        crop_x = int((new_w - w) * (start_pt[0] + (end_pt[0] - start_pt[0]) * progress))
        crop_y = int((new_h - h) * (start_pt[1] + (end_pt[1] - start_pt[1]) * progress))
        cropped_img = resized_img[crop_y:crop_y + h, crop_x:crop_x + w]

        if text1:
            cropped_img = overlay_text_on_frame(cropped_img, text1, text1_pos, font_file, font_sz, color, border_color,
                                                border_sz, max_width=max_width)

        if text2 and frame_num >= start_fade_frame:
            fade_progress = (frame_num - start_fade_frame) / (end_fade_frame - start_fade_frame)
            fade_progress = min(fade_progress, 1.0)
            cropped_img = overlay_text_on_frame(cropped_img, text2, text2_pos, font_file, font_sz, color, border_color,
                                                border_sz, alpha=fade_progress, max_width=max_width)

        video_writer.write(cropped_img)

    video_writer.release()

    if audio_file:
        video_clip = VideoFileClip('temp_video.mp4')
        audio_clip = AudioFileClip(audio_file).subclip(epic_part_of_audio - 6, epic_part_of_audio - 6 + duration)
        audio_clip = audio_clip.audio_fadeout(3)
        final_video = video_clip.set_audio(audio_clip)
        final_video.write_videofile(output_vid, codec='libx264', audio_codec='aac')
    else:
        import os
        os.rename('temp_video.mp4', output_vid)

no_upscale = {
    "duration":3,
    "fps":80,
    "start_zoom":1,
    "end_zoom":1.8,
    "start_pt":(0, 1),  # Top-left corner
    "end_pt":(1, 0),  # Bottom-right corner
    #use_effect=True,  # Apply epic effect
    "text1":"You never know how strong you are",  # Initial text to add
    "text1_pos":(50, 100),  # Position of the initial text
    "text2":"until being strong is your only choice",  # Second text to add with fade-in
    "text2_pos":(50, 200),  # Position of the second text
    "font_file":'League_Spartan/static/LeagueSpartan-Bold.ttf',  # Path to the Montserrat font
    "font_sz":36,  # Size of the font
    "color":(255, 255, 255),  # Color of the text (white)
    "border_color":(0, 0, 0),  # Color of the text border (black)
    "border_sz":2,  # Width of the text border
    "audio_file":'Inner Strength.mp3',  # Path to the audio file
    "max_width" : 375,  # Maximum width for text wrapping
    "upscale_factor": 1.0,
    "start_audio_sec": 27
}

source = config['image_source']
text1_pos = None
start_pt = CORNERS_ENUMS[config['start_pt']]
end_pt = tuple(1 - x for x in start_pt)
img_suffix = None

if source == 'playground':
    text1_pos = (50, 400)
    img_suffix = '.png'


elif source == 'ideogram':
    text1_pos = (50, 420)
    img_suffix = '.jpeg'

if config['epic_part_of_audio'] < 6:
    print("epic pert of audio can't be less than 6, using 6 as value")
    config['epic_part_of_audio'] = 6

upscaled = {
    "duration": 12,
    "fps": 60,
    "start_zoom": 1,
    "end_zoom": 1.8,
    "start_pt": start_pt,  # Bottom-right corner
    "end_pt": end_pt,  # Top-left corner
    #use_effect=True,  # Apply epic effect
    "text1": config['text1'],
    "text1_pos": text1_pos,
    "text2": config['text2'],
    "text2_pos": (50, text1_pos[1] + config['text_y_diff'],),
    "font_file":'League_Spartan/static/LeagueSpartan-Bold.ttf',  # Path to the Montserrat font
    "font_sz": 36*4,  # Size of the font
    "color": tuple(config['color']),  # Color of the text (white)
    "border_color": tuple(config['border_color']),  # Color of the text border (black)
    "border_sz": 4,  # Width of the text border
    "audio_file": '4.music/' + config['audio_file'] + '.mp3',  # Path to the audio file
    "max_width": 375*4,  # Maximum width for text wrapping
    "upscale_factor": 1.0,
    "epic_part_of_audio": config['epic_part_of_audio']
}

t = time.time()
# Example usage
create_ken_burns_video(
    '1.base_images/' + config['image_name'],
    '5.videos/' + config['image_name'] + '.mp4',
    **upscaled,
)
print(time.time() - t, 'seconds to complete video creation')
