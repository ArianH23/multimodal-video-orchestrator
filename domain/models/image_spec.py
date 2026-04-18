from dataclasses import dataclass


@dataclass
class ImageSpecification:
    image_path: str
    output_path: str
    topic: str
    text1: str
    text2: str
    text_diff_mult: int
    color: list
    border_color: list
