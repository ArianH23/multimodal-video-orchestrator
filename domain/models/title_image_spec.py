from dataclasses import dataclass

@dataclass
class TitleImageSpecification:
    image_path: str
    output_path: str
    topic: str
    title_text: str
    color: tuple
    border_color: tuple
