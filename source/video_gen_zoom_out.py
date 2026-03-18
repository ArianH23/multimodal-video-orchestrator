import time
import json
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_audioclips, CompositeAudioClip
from moviepy.audio.AudioClip import AudioArrayClip
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing
import math
from multiprocessing import shared_memory
import pickle

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


_text_cache = None
_current_shm_name = None


def process_frame_with_shm(frame_num, total_frames, zoom_out_duration, fps, w, h, img,
                           start_pt, end_pt, start_zoom, end_zoom, start_fade_frame,
                           end_fade_frame, overlay_image, overlay_width, overlay_height,
                           duration, queue, shm_name, cache_size):
    global _text_cache, _current_shm_name

    # Load cache from shared memory (only once per worker)
    if _text_cache is None or _current_shm_name != shm_name:
        shm = shared_memory.SharedMemory(name=shm_name)
        cache_bytes = bytes(shm.buf[:cache_size])
        _text_cache = pickle.loads(cache_bytes)
        _current_shm_name = shm_name
        shm.close()  # Don't unlink, just close our handle

    # Ken Burns zoom logic
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

    # Convert to PIL
    pil_image = Image.fromarray(cv2.cvtColor(cropped_img, cv2.COLOR_BGR2RGB)).convert('RGBA')

    # Grab pre-rendered text from LOCAL cache (loaded from shared memory)
    if frame_num < start_fade_frame:
        text_layer_np = _text_cache['text1_only']
    elif frame_num >= end_fade_frame:
        text_layer_np = _text_cache['both_texts']
    else:
        fade_index = int(frame_num - start_fade_frame)
        text_layer_np = _text_cache['fade_frames'][fade_index]

    # Composite
    text_layer = Image.fromarray(text_layer_np)
    pil_image = Image.alpha_composite(pil_image, text_layer)

    if overlay_image:
        x_position = w - overlay_width - 50
        y_position = h - overlay_height - 10
        pil_image.paste(overlay_image, (x_position, y_position), overlay_image)

    cropped_img = cv2.cvtColor(np.array(pil_image.convert('RGB')), cv2.COLOR_RGB2BGR)

    queue.put(1)
    return frame_num, cropped_img

def process_frame_optimized(frame_num, total_frames, zoom_out_duration, fps, w, h, img,
                            start_pt, end_pt, start_zoom, end_zoom, start_fade_frame,
                            end_fade_frame, overlay_image, overlay_width, overlay_height,
                            duration, queue, text_layer_cache):
    # Ken Burns zoom logic
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

    # Convert to PIL
    pil_image = Image.fromarray(cv2.cvtColor(cropped_img, cv2.COLOR_BGR2RGB)).convert('RGBA')

    # Grab pre-rendered text from SHARED cache
    if frame_num < start_fade_frame:
        text_layer_np = text_layer_cache['text1_only']
    elif frame_num >= end_fade_frame:
        text_layer_np = text_layer_cache['both_texts']
    else:
        fade_index = int(frame_num - start_fade_frame)
        text_layer_np = text_layer_cache['fade_frames'][fade_index]

    # Composite
    text_layer = Image.fromarray(text_layer_np)
    pil_image = Image.alpha_composite(pil_image, text_layer)

    if overlay_image:
        x_position = w - overlay_width - 50
        y_position = h - overlay_height - 10
        pil_image.paste(overlay_image, (x_position, y_position), overlay_image)

    cropped_img = cv2.cvtColor(np.array(pil_image.convert('RGB')), cv2.COLOR_RGB2BGR)

    queue.put(1)
    return frame_num, cropped_img

def create_text_overlay_layer(w, h, text1, text1_pos, text2, text2_pos, font_file, font_sz,
                               color, border_color, border_sz, max_width, alpha=1.0):
    """Pre-render a text overlay layer that can be reused across frames"""
    text_layer = Image.new('RGBA', (w, h), (255, 255, 255, 0))
    draw = ImageDraw.Draw(text_layer)
    font = ImageFont.truetype(font_file, font_sz)

    # Draw text1
    if text1:
        lines = wrap_text(text1, font, max_width) if max_width else [text1]
        y = text1_pos[1]
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            text_width = bbox[2] - bbox[0]
            line_pos = ((w - text_width) // 2, y)
            draw_text_with_border(draw, line, line_pos, font, color, border_color, border_sz)
            y += font_sz + border_sz * 2

    # Draw text2
    if text2:
        lines = wrap_text(text2, font, max_width) if max_width else [text2]
        y = text2_pos[1]
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            text_width = bbox[2] - bbox[0]
            line_pos = ((w - text_width) // 2, y)
            draw_text_with_border(draw, line, line_pos, font, color, border_color, border_sz)
            y += font_sz + border_sz * 2

    # Apply alpha if needed
    if alpha < 1.0:
        text_layer_np = np.array(text_layer)
        text_layer_np[..., 3] = (text_layer_np[..., 3] * alpha).astype(np.uint8)
        text_layer = Image.fromarray(text_layer_np)

    return text_layer


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

    (width, baseline), (offset_x, offset_y) = font.font.getsize(text)
    ascent, descent = font.getmetrics()

    text_mask = Image.new('L', (width, ascent + descent), 0)
    mask_draw = ImageDraw.Draw(text_mask)
    mask_draw.text((0, 0), text, font=font, fill=255)

    # Only draw at cardinal and diagonal directions
    offsets = []
    for angle in range(0, 360, 45):  # 8 directions instead of 49
        dx = int(border_width * math.cos(math.radians(angle)))
        dy = int(border_width * math.sin(math.radians(angle)))
        offsets.append((dx, dy))

    for dx, dy in offsets:
        draw.bitmap((x + dx, y + dy), text_mask, fill=border_color)

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


def process_frame(frame_num, total_frames, zoom_out_duration, fps, w, h, img, start_pt, end_pt,
                  start_zoom, end_zoom, text1, text1_pos, text2, text2_pos, start_fade_frame,
                  end_fade_frame, font_file, font_sz, color, border_color, border_sz, max_width,
                  overlay_image, overlay_width, overlay_height, duration, queue,
                  text_layer_cache):
    # [Ken Burns zoom logic - unchanged]
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

    # Convert to PIL
    pil_image = Image.fromarray(cv2.cvtColor(cropped_img, cv2.COLOR_BGR2RGB)).convert('RGBA')

    # Select appropriate text layer (they're numpy arrays now)
    if frame_num < start_fade_frame:
        text_layer_np = text_layer_cache['text1_only']
    elif frame_num >= end_fade_frame:
        text_layer_np = text_layer_cache['both_texts']
    else:
        # Fading text2
        fade_progress = (frame_num - start_fade_frame) / (end_fade_frame - start_fade_frame)
        fade_progress = min(fade_progress, 1.0)

        # Combine text1 + fading text2
        text_layer_np = text_layer_cache['text1_only'].copy()
        text2_np = text_layer_cache['text2_only'].copy()
        text2_np[..., 3] = (text2_np[..., 3] * fade_progress).astype(np.uint8)

        # Alpha composite manually in numpy (faster than PIL for this)
        alpha_text2 = text2_np[..., 3:4] / 255.0
        alpha_base = text_layer_np[..., 3:4] / 255.0
        alpha_out = alpha_text2 + alpha_base * (1 - alpha_text2)

        for c in range(3):  # RGB channels
            text_layer_np[..., c] = (
                    (text2_np[..., c] * alpha_text2[..., 0] +
                     text_layer_np[..., c] * alpha_base[..., 0] * (1 - alpha_text2[..., 0])) /
                    (alpha_out[..., 0] + 1e-6)
            ).astype(np.uint8)

        text_layer_np[..., 3] = (alpha_out[..., 0] * 255).astype(np.uint8)

    # Convert text layer back to PIL and composite
    text_layer = Image.fromarray(text_layer_np)
    pil_image = Image.alpha_composite(pil_image, text_layer)

    # Add overlay image
    if overlay_image:
        x_position = w - overlay_width - 50
        y_position = h - overlay_height - 10
        pil_image.paste(overlay_image, (x_position, y_position), overlay_image)

    cropped_img = cv2.cvtColor(np.array(pil_image.convert('RGB')), cv2.COLOR_RGB2BGR)

    queue.put(1)
    return frame_num, cropped_img


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

    print("Pre-rendering text layers...")

    # Pre-render all text layers as numpy arrays
    text_layers = {}

    if text1:
        text_layers['text1_only'] = np.array(create_text_overlay_layer(
            w, h, text1, text1_pos, None, None, font_file, font_sz,
            color, border_color, border_sz, max_width
        ))

    if text1 and text2:
        text_layers['both_texts'] = np.array(create_text_overlay_layer(
            w, h, text1, text1_pos, text2, text2_pos, font_file, font_sz,
            color, border_color, border_sz, max_width
        ))

    # Pre-render fade frames
    fade_frame_count = int(end_fade_frame - start_fade_frame)
    fade_frames_list = []

    if text2:
        text2_layer = create_text_overlay_layer(
            w, h, None, None, text2, text2_pos, font_file, font_sz,
            color, border_color, border_sz, max_width
        )

        for i in range(fade_frame_count + 1):
            fade_progress = i / fade_frame_count
            combined = text_layers['text1_only'].copy()
            combined_pil = Image.fromarray(combined)

            text2_faded = text2_layer.copy()
            text2_np = np.array(text2_faded)
            text2_np[..., 3] = (text2_np[..., 3] * fade_progress).astype(np.uint8)
            text2_faded = Image.fromarray(text2_np)

            combined_pil = Image.alpha_composite(combined_pil, text2_faded)
            fade_frames_list.append(np.array(combined_pil))

    text_layers['fade_frames'] = fade_frames_list
    print(f"Pre-rendered {len(fade_frames_list)} fade frames")

    # SERIALIZE the entire cache once and put in shared memory
    cache_bytes = pickle.dumps(text_layers)
    cache_size = len(cache_bytes)
    print(f"Text cache size: {cache_size / 1024 / 1024:.1f} MB")

    # Create shared memory block
    shm = shared_memory.SharedMemory(create=True, size=cache_size)
    shm.buf[:cache_size] = cache_bytes

    # Pass only the NAME of the shared memory (tiny string!)
    shm_name = shm.name

    with multiprocessing.Manager() as manager:
        queue = manager.Queue()

        progress_process = multiprocessing.Process(target=progress_updater, args=(queue, total_frames))
        progress_process.start()

        frames_dict = {}
        with ProcessPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(
                    process_frame_with_shm,  # New function
                    frame_num, total_frames, zoom_out_duration, fps, w, h, img,
                    start_pt, end_pt, start_zoom, end_zoom, start_fade_frame,
                    end_fade_frame, overlay_image, overlay_width, overlay_height,
                    duration, queue, shm_name, cache_size  # Just pass name and size!
                ): frame_num for frame_num in range(total_frames)
            }

            for future in as_completed(futures):
                frame_num, frame = future.result()
                frames_dict[frame_num] = frame

        progress_process.join()

        # Write frames in order
        video_writer = cv2.VideoWriter('temp_video.mp4', fourcc, fps, (w, h))
        for frame_num in sorted(frames_dict.keys()):
            video_writer.write(frames_dict[frame_num])
        video_writer.release()

        # Cleanup shared memory
        shm.close()
        shm.unlink()


    if audio_file:
        video_clip = VideoFileClip('temp_video.mp4')
        # audio_clip = AudioFileClip(audio_file).subclip(epic_part_of_audio - start_fade_in, epic_part_of_audio - start_fade_in + duration)
        # audio_clip = audio_clip.audio_fadeout(3)
        # final_video = video_clip.set_audio(audio_clip)
        # final_video.write_videofile(output_vid, codec='libx264', audio_codec='aac')
        background_audio = AudioFileClip(audio_file).subclip(epic_part_of_audio - (start_fade_frame // fps),
                                                             epic_part_of_audio - (start_fade_frame // fps) + duration + zoom_out_duration)
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


def generate_video(image_name, input_image_path, output_video_path, starting_corner, start_fade_in, epic_part_of_audio, topic, fps, quotes, text_y_mult,
                   border_color, audio_file):

    start_pt = CORNERS_ENUMS[starting_corner]
    end_pt = tuple(1 - x for x in start_pt)

    text_y_offset = 150 * text_y_mult
    text1_pos = (50, 400)

    if epic_part_of_audio < start_fade_in:
        print(f"epic pert of audio can't be less than {start_fade_in}, using {start_fade_in} as value")
        epic_part_of_audio = start_fade_in


    topics_rgb_map = json.load(open('topics.json'))


    color = topics_rgb_map[topic.lower()]


    parameters = {
        "duration": 12,
        "fps": fps,
        "start_zoom": 1,
        "end_zoom": 1.8,
        "start_pt": start_pt,
        "end_pt": end_pt,
        "text1": quotes['text1'],
        "text1_pos": text1_pos,
        "text2": quotes['text2'],
        "text2_pos": (50, text1_pos[1] + text_y_offset,),
        "font_file": 'font/League_Spartan/static/LeagueSpartan-Bold.ttf',
        "font_sz": 36*4,
        "color": tuple(color),
        "border_color": tuple(border_color),
        "border_sz": 4,
        "audio_file": audio_file,
        "max_width": 325*4,
        "upscale_factor": 1.0,
        "epic_part_of_audio": epic_part_of_audio,
        "overlay_image_path": 'logo.png',
        "overlay_scale_factor": 0.75,
        "start_fade_in": start_fade_in,
        "fade_with_voice": True,
    }

    t = time.time()
    json_path = 'data/done_jsons/' + image_name.replace('.', '-') + '.json'

    config = {
        "image_name": image_name,
        "starting_corner": starting_corner,
        "start_fade_in": start_fade_in,
        "epic_part_of_audio": epic_part_of_audio,
        "title": topic,
        "fps": fps,
        "quotes": quotes,
        "text_y_mult": text_y_mult,
        "border_color": border_color,
        "audio_file": audio_file
    }

    with open(json_path, 'w') as file:
        json.dump(config, file, indent=4)


    create_ken_burns_video(
        input_image_path,
        output_video_path,
        image_name,
        **parameters,
    )
    print(time.time() - t, 'seconds to complete video creation')
