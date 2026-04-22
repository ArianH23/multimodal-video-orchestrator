from dataclasses import dataclass
from typing import List


@dataclass
class AudioDropAnalysis:
    main_drop: float
    all_drops: List[float]
    top3: List[float]
    confidence: float
    build_up_start: float
