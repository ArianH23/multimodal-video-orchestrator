from dataclasses import dataclass

@dataclass
class VideoSpecification:
    image_path: str
    audio_path: str
    voice1_path: str
    voice2_path: str
    output_path: str
    color: [int, int, int]
    border_color: [int, int, int]
    text1: str
    text2: str
    starting_corner: str
    fps: int
    duration: int
    start_fade_in: int
    epic_part_of_audio: int
    pause_between_fades: int
    text_y_offset_mult: int

