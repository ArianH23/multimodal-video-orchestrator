from domain.ports.video_renderer import VideoRendererPort
from domain.ports.storage import StoragePort
from domain.models.video_spec import VideoSpecification


class VideoOrchestratorService:
    def __init__(self, video_renderer: VideoRendererPort, storage: StoragePort):
        self.video_renderer = video_renderer
        self.storage = storage

    def compile_final_content(self, title: str, quotes: dict, image_path: str,
                              audio_path: str, voice_paths: list, starting_corner: str, border_color: list,
                              color: list, epic_part_of_audio: int, pause_between_fades: int,
                              start_fade_in: int, fps: int, duration: int, text_y_offset_mult: int) -> str:
        print(f"Orchestrating final video for {title}...")

        temp_video_path = f"temp_render_{title}.mp4"

        spec = VideoSpecification(
            image_path=image_path,
            audio_path=audio_path,
            voice1_path=voice_paths[0],
            voice2_path=voice_paths[1],
            output_path=temp_video_path,
            text1=quotes['text1'],
            text2=quotes['text2'],
            starting_corner=starting_corner,
            fps=fps,
            duration=duration,
            start_fade_in=start_fade_in,
            epic_part_of_audio=epic_part_of_audio,
            color=color,
            border_color=border_color,
            pause_between_fades=pause_between_fades
            # text_y_offset_mult=text_y_offset_mult
        )

        rendered_temp_path = self.video_renderer.render_video(spec)

        final_destination = f"data/videos/{title}.mp4"
        print(f"Moving temporary render to final destination: {final_destination}")

        final_video_path = self.storage.move(rendered_temp_path, final_destination)

        print(f"Video compiled and stored successfully at {final_video_path}")
        return final_video_path
