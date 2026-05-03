from dataclasses import dataclass
from typing import List

@dataclass
class TrendSource:
    title: str
    url: str

@dataclass
class TrendReport:
    summary: str
    sources: List[TrendSource]

# domain/models/topic.py
from dataclasses import dataclass

@dataclass
class MotivationalTopic:
    name: str
    color_rgb: str