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

from domain.ports.video_renderer import VideoRendererPort
from domain.models.video_spec import VideoSpecification

new_width = 1472
new_height = 2624

CORNERS_ENUMS = {
    "TR": (1, 0),
    "BL": (0, 1),
    "TL": (0, 0),
    "BR": (1, 1),
}


_text_cache = None
_current_shm_name = None


class OpenCVVideoAdapter(VideoRendererPort):
    def __init__(self, font_path: str, logo_path: str):
        self.font_path = font_path
        self.logo_path = logo_path

    def _process_frame_with_shm(self, frame_num, total_frames, zoom_out_duration, fps, w, h, img,
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

    def _create_text_overlay_layer(self, w, h, text1, text1_pos, text2, text2_pos, font_file, font_sz,
                                   color, border_color, border_sz, max_width, alpha=1.0):
        text_layer = Image.new('RGBA', (w, h), (255, 255, 255, 0))
        draw = ImageDraw.Draw(text_layer)
        font = ImageFont.truetype(font_file, font_sz)

        # Draw text1
        if text1:
            lines = self._wrap_text(text1, font, max_width) if max_width else [text1]
            y = text1_pos[1]
            for line in lines:
                bbox = draw.textbbox((0, 0), line, font=font)
                text_width = bbox[2] - bbox[0]
                line_pos = ((w - text_width) // 2, y)
                self._draw_text_with_border(draw, line, line_pos, font, color, border_color, border_sz)
                y += font_sz + border_sz * 2

        # Draw text2
        if text2:
            lines = self._wrap_text(text2, font, max_width) if max_width else [text2]
            y = text2_pos[1]
            for line in lines:
                bbox = draw.textbbox((0, 0), line, font=font)
                text_width = bbox[2] - bbox[0]
                line_pos = ((w - text_width) // 2, y)
                self._draw_text_with_border(draw, line, line_pos, font, color, border_color, border_sz)
                y += font_sz + border_sz * 2

        # Apply alpha if needed
        if alpha < 1.0:
            text_layer_np = np.array(text_layer)
            text_layer_np[..., 3] = (text_layer_np[..., 3] * alpha).astype(np.uint8)
            text_layer = Image.fromarray(text_layer_np)

        return text_layer

    def _draw_text_with_border(self, draw, text, pos, font, fill, border_color, border_width):
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

    def _enhance_image(self, img):
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

    def _progress_updater(self, queue, total_frames):
        """Reads from the queue and prints progress updates."""
        processed_frames = 0
        while processed_frames < total_frames:
            queue.get()  # Wait for a signal from a worker
            processed_frames += 1
            if processed_frames % 10 == 0:
                print(f"Processed: {processed_frames}/{total_frames}")

    def _generate_silence(self, duration=1, fps=44100):
        silent_array = np.zeros((int(fps * duration), 2))  # Stereo silence
        return AudioArrayClip(silent_array, fps=fps)

    def _create_ken_burns_video(self, input_img, output_vid, voice1_path, voice2_path, duration=10, fps=30,
                                start_zoom=1.0,
                                end_zoom=2.0,
                                use_effect=False, text1=None, text1_pos=(50, 50), text2=None,
                                text2_pos=(50, 100), font_file='Montserrat-Regular.ttf', font_sz=32,
                                color=(255, 255, 255),
                                border_color=(0, 0, 0), border_sz=2, audio_file=None, max_width=None,
                                epic_part_of_audio=6,
                                overlay_image_path=None, overlay_scale_factor=0.2, start_fade_in=6,
                                fade_with_voice=False,
                                zoom_out_duration=4,
                                starting_corner='BL',
                                pause_between_fades=0.5):
        start_pt = CORNERS_ENUMS[starting_corner]
        end_pt = tuple(1 - x for x in start_pt)

        img = cv2.imread(input_img, cv2.IMREAD_UNCHANGED)
        img = cv2.resize(img, (new_width, new_height))

        if use_effect:
            img = self._enhance_image(img)

        additional_audio_clip1 = AudioFileClip(voice1_path)
        additional_audio_clip2 = AudioFileClip(voice2_path)

        duration_of_first_audio = additional_audio_clip1.duration
        duration_of_second_audio = additional_audio_clip2.duration
        start_silence_duration = 0.3
        silent_clip1 = self._generate_silence(duration=1)
        silent_clip3 = self._generate_silence(duration=start_silence_duration)

        h, w, _ = img.shape
        total_frames = duration * fps + zoom_out_duration * fps
        if fade_with_voice:
            start_fade_frame = (start_silence_duration + duration_of_first_audio + pause_between_fades) * fps
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
            text_layers['text1_only'] = np.array(self._create_text_overlay_layer(
                w, h, text1, text1_pos, None, None, font_file, font_sz,
                color, border_color, border_sz, max_width
            ))

        if text1 and text2:
            text_layers['both_texts'] = np.array(self._create_text_overlay_layer(
                w, h, text1, text1_pos, text2, text2_pos, font_file, font_sz,
                color, border_color, border_sz, max_width
            ))

        # Pre-render fade frames
        fade_frame_count = int(end_fade_frame - start_fade_frame)
        fade_frames_list = []

        if text2:
            text2_layer = self._create_text_overlay_layer(
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

            progress_process = multiprocessing.Process(target=self._progress_updater, args=(queue, total_frames))
            progress_process.start()

            frames_dict = {}
            with ProcessPoolExecutor(max_workers=2) as executor:
                futures = {
                    executor.submit(
                        self._process_frame_with_shm,  # New function
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

            background_audio = AudioFileClip(audio_file).subclip(epic_part_of_audio - (start_fade_frame // fps),
                                                                 epic_part_of_audio - (
                                                                         start_fade_frame // fps) + duration + zoom_out_duration)
            background_audio = background_audio.audio_fadeout(2)
            background_audio = background_audio.volumex(0.325)

            additional_audio_clip1 = additional_audio_clip1
            additional_audio_clip2 = additional_audio_clip2

            combined_additional_audio = concatenate_audioclips(
                [silent_clip3, additional_audio_clip1, silent_clip1, additional_audio_clip2])
            final_audio = CompositeAudioClip([background_audio, combined_additional_audio.set_start(
                0)])  # set_start(0) ensures it starts at the beginning
            final_video = video_clip.set_audio(final_audio)

            final_video.write_videofile(output_vid, codec='libx264', audio_codec='aac')

        else:
            import os
            os.rename('temp_video.mp4', output_vid)

    def render_video(self, spec: VideoSpecification) -> str:
        """This replaces your old generate_video function."""

        color = spec.color
        border_color = spec.border_color

        text_y_offset = 150 * spec.text_y_offset_mult
        text1_pos = (50, 400)

        self._create_ken_burns_video(
            input_img=spec.image_path,
            output_vid=spec.output_path,
            voice1_path=spec.voice1_path,
            voice2_path=spec.voice2_path,
            text1=spec.text1,
            text2=spec.text2,
            text1_pos=text1_pos,
            text2_pos=(50, text1_pos[1] + text_y_offset,),
            duration=spec.duration,
            audio_file=spec.audio_path,
            font_file=self.font_path,
            color=tuple(color),
            border_color=tuple(border_color),
            border_sz=2,
            font_sz=36*4,
            max_width=325 * 4,
            epic_part_of_audio=spec.epic_part_of_audio,
            overlay_image_path=self.logo_path,
            overlay_scale_factor=0.75,
            start_fade_in=6,
            fade_with_voice=True,
            zoom_out_duration=4,
            pause_between_fades=spec.pause_between_fades,
            fps=spec.fps
        )

        return spec.output_path
