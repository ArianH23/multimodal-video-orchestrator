import time
import json
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_audioclips, CompositeAudioClip
from moviepy.audio.AudioClip import AudioArrayClip
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing


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


CORNERS_ENUMS ={
    "TR": (1, 0),
    "BL": (0, 1),
    "TL": (0, 0),
    "BR": (1, 1),
}

new_width = 1472  # Width in pixels
new_height = 2624  # Height in pixels

def add_image_to_frame(frame, overlay_image, position):
    # Convert the frame to a PIL image
    pil_frame = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

    # Convert the overlay image to RGBA if it isn't already
    if overlay_image.mode != 'RGBA':
        overlay_image = overlay_image.convert('RGBA')

    # Determine the position to place the overlay image
    x_offset, y_offset = position

    # Paste the overlay image onto the frame with transparency handling
    pil_frame.paste(overlay_image, (x_offset, y_offset), overlay_image)

    # Convert the PIL image back to an OpenCV image
    return cv2.cvtColor(np.array(pil_frame), cv2.COLOR_RGB2BGR)


def generate_silence(duration=1, fps=44100):
    silent_array = np.zeros((int(fps * duration), 2))  # Stereo silence
    return AudioArrayClip(silent_array, fps=fps)


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


def process_frame(frame_num, total_frames, zoom_out_duration, fps, w, h, img, start_pt, end_pt, start_zoom, end_zoom,
                  text1, text1_pos, text2, text2_pos, start_fade_frame, end_fade_frame, font_file, font_sz,
                  color, border_color, border_sz, max_width, overlay_image, overlay_width, overlay_height, duration, queue):
    if frame_num < total_frames - zoom_out_duration * fps:
        progress = frame_num / ((total_frames) - zoom_out_duration * fps)
        zoom = start_zoom + (end_zoom - start_zoom) * progress
        new_w = int(w * zoom)
        new_h = int(h * zoom)

        resized_img = cv2.resize(img, (new_w, new_h))
        crop_x = int((new_w - w) * (start_pt[0] + (end_pt[0] - start_pt[0]) * progress))
        crop_y = int((new_h - h) * (start_pt[1] + (end_pt[1] - start_pt[1]) * progress))
        cropped_img = resized_img[crop_y:crop_y + h, crop_x:crop_x + w]
    else:
        progress = (frame_num - duration * fps) / (zoom_out_duration * fps)
        zoom = end_zoom - (end_zoom - start_zoom) * progress
        new_w = int(w * zoom)
        new_h = int(h * zoom)
        cropped_img = cv2.resize(img, (new_w, new_h))
        crop_x = int((new_w - w) * (end_pt[0] + (-end_pt[0]) * progress))
        crop_y = int((new_h - h) * (end_pt[1] + (-end_pt[1]) * progress))
        cropped_img = cropped_img[crop_y:crop_y + h, crop_x:crop_x + w]

    if text1:
        cropped_img = overlay_text_on_frame(cropped_img, text1, text1_pos, font_file, font_sz, color, border_color,
                                            border_sz, max_width=max_width)

    if text2 and frame_num >= start_fade_frame:
        fade_progress = (frame_num - start_fade_frame) / (end_fade_frame - start_fade_frame)
        fade_progress = min(fade_progress, 1.0)
        cropped_img = overlay_text_on_frame(cropped_img, text2, text2_pos, font_file, font_sz, color, border_color,
                                            border_sz, alpha=fade_progress, max_width=max_width)

    if overlay_image:
        x_position = w - overlay_width - 50
        y_position = h - overlay_height - 10
        cropped_img = add_image_to_frame(cropped_img, overlay_image, (x_position, y_position))

    queue.put(1)  # Notify the progress updater

    return frame_num, cropped_img  # Return tuple for ordering

def progress_updater(queue, total_frames):
    """Reads from the queue and prints progress updates."""
    processed_frames = 0
    while processed_frames < total_frames:
        queue.get()  # Wait for a signal from a worker
        processed_frames += 1
        if processed_frames % 10 == 0:
            print(f"Processed: {processed_frames}/{total_frames}")

def create_ken_burns_video(input_img, output_vid, image_name, duration=10, fps=30, start_zoom=1.0, end_zoom=2.0, start_pt=(0, 0),
                           end_pt=(1, 1), use_effect=False, text1=None, text1_pos=(50, 50), text2=None,
                           text2_pos=(50, 100), font_file='Montserrat-Regular.ttf', font_sz=32, color=(255, 255, 255),
                           border_color=(0, 0, 0), border_sz=2, audio_file=None, max_width=None, upscale_factor=1.0, epic_part_of_audio=6,
                           overlay_image_path=None,  overlay_scale_factor=0.2, start_fade_in=6, fade_with_voice=False, zoom_out_duration=4):
    img = cv2.imread(input_img, cv2.IMREAD_UNCHANGED)
    img = cv2.resize(img, (new_width, new_height))

    if use_effect:
        img = enhance_image(img)

    additional_audio_clip1 = AudioFileClip(f"7.voices/{image_name}/voice1.mp3")
    additional_audio_clip2 = AudioFileClip(f"7.voices/{image_name}/voice2.mp3")

    duration_of_first_audio = additional_audio_clip1.duration
    duration_of_second_audio = additional_audio_clip2.duration
    start_silence_duration = 0.3
    silent_clip1 = generate_silence(duration=1)
    silent_clip3 = generate_silence(duration=start_silence_duration)

    h, w, _ = img.shape
    total_frames = duration * fps + zoom_out_duration * fps
    if fade_with_voice:
        start_fade_frame = (start_silence_duration + duration_of_first_audio +0.5)*fps
    else:
        start_fade_frame = start_fade_in * fps

    end_fade_frame = start_fade_frame + 2 * fps

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    video_writer = cv2.VideoWriter('temp_video.mp4', fourcc, fps, (w, h))

    overlay_image = None
    if overlay_image_path:
        overlay_image = Image.open(overlay_image_path).convert("RGBA")
        overlay_width, overlay_height = overlay_image.size
        overlay_image = overlay_image.resize(
            (int(overlay_width * overlay_scale_factor), int(overlay_height * overlay_scale_factor)),

        )
        overlay_width, overlay_height = overlay_image.size

    with multiprocessing.Manager() as manager:
        queue = manager.Queue()  # Shared queue

        # Start a separate process to update progress
        progress_process = multiprocessing.Process(target=progress_updater, args=(queue, total_frames))
        progress_process.start()

        with ProcessPoolExecutor(max_workers=8) as executor:
            futures = {executor.submit(process_frame, frame_num, total_frames, zoom_out_duration, fps, w, h, img, start_pt,
                                       end_pt, start_zoom, end_zoom, text1, text1_pos, text2, text2_pos, start_fade_frame,
                                       end_fade_frame, font_file, font_sz, color, border_color, border_sz, max_width,
                                       overlay_image, overlay_width, overlay_height, duration, queue)
                       for frame_num in range(total_frames)}

            for future in as_completed(futures):
                frame_num, frame = future.result()
                if frame is not None:  # Avoid writing corrupted frames
                    video_writer.write(frame)

    video_writer.release()

    if audio_file:
        video_clip = VideoFileClip('temp_video.mp4')
        # audio_clip = AudioFileClip(audio_file).subclip(epic_part_of_audio - start_fade_in, epic_part_of_audio - start_fade_in + duration)
        # audio_clip = audio_clip.audio_fadeout(3)
        # final_video = video_clip.set_audio(audio_clip)
        # final_video.write_videofile(output_vid, codec='libx264', audio_codec='aac')
        background_audio = AudioFileClip(audio_file).subclip(epic_part_of_audio - start_fade_in,
                                                             epic_part_of_audio - start_fade_in + duration + zoom_out_duration)
        background_audio = background_audio.audio_fadeout(2)
        background_audio = background_audio.volumex(0.325)

        additional_audio_clip1 = additional_audio_clip1
        additional_audio_clip2 = additional_audio_clip2

        combined_additional_audio = concatenate_audioclips([silent_clip3, additional_audio_clip1, silent_clip1, additional_audio_clip2])
        final_audio = CompositeAudioClip([background_audio, combined_additional_audio.set_start(0)])  # set_start(0) ensures it starts at the beginning
        final_video = video_clip.set_audio(final_audio)

        final_video.write_videofile(output_vid, codec='libx264', audio_codec='aac')

    else:
        import os
        os.rename('temp_video.mp4', output_vid)


def generate_video(image_name, starting_corner, start_fade_in, epic_part_of_audio, title, fps, quotes, text_y_mult,
                   border_color, audio_file):

    start_pt = CORNERS_ENUMS[starting_corner]
    end_pt = tuple(1 - x for x in start_pt)
    img_suffix = None
    text_y_offset = 150 * text_y_mult
    text1_pos = (50, 400)

    if epic_part_of_audio < start_fade_in:
        print(f"epic pert of audio can't be less than {start_fade_in}, using {start_fade_in} as value")
        epic_part_of_audio = start_fade_in


    topics_rgb_map = json.load(open('topics.json'))


    color = topics_rgb_map[title.lower()]


    upscaled = {
        "duration": 12,
        "fps": fps,
        "start_zoom": 1,
        "end_zoom": 1.8,
        "start_pt": start_pt,  # Bottom-right corner
        "end_pt": end_pt,  # Top-left corner
        #use_effect=True,  # Apply epic effect
        "text1": quotes['text1'],
        "text1_pos": text1_pos,
        "text2": quotes['text2'],
        "text2_pos": (50, text1_pos[1] + text_y_offset,),
        "font_file":'League_Spartan/static/LeagueSpartan-Bold.ttf',  # Path to the Montserrat font
        "font_sz": 36*4,  # Size of the font
        "color": tuple(color),  # Color of the text (white)
        "border_color": tuple(border_color),  # Color of the text border (black)
        "border_sz": 4,  # Width of the text border
        "audio_file": '4.music/' + audio_file + '.mp3',  # Path to the audio file
        "max_width": 325*4,  # Maximum width for text wrapping
        "upscale_factor": 1.0,
        "epic_part_of_audio": epic_part_of_audio,
        "overlay_image_path": 'logo.png',  # Path to the overlay image (e.g., a logo)
        "overlay_scale_factor": 0.75,  # Smaller scale factor for the overlay image
        "start_fade_in": start_fade_in,
        "fade_with_voice": True,
    }

    t = time.time()
    json_path = '6.done_jsons/' + image_name.replace('.', '-') + '.json'

    config = {
        "image_name": image_name,
        "starting_corner": starting_corner,
        "start_fade_in": start_fade_in,
        "epic_part_of_audio": epic_part_of_audio,
        "title": title,
        "fps": fps,
        "quotes": quotes,
        "text_y_mult": text_y_mult,
        "border_color": border_color,
        "audio_file": audio_file
    }

    with open(json_path, 'w') as file:
        json.dump(config, file, indent=4)


    create_ken_burns_video(
        '1.base_images/' + image_name + '.png',
        '5.videos/' + image_name + '.mp4',
        image_name,
        **upscaled,
    )
    print(time.time() - t, 'seconds to complete video creation')
