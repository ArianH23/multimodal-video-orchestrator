from abc import ABC, abstractmethod
from domain.models.audio_analysis import AudioDropAnalysis


class AudioAnalyzerPort(ABC):
    @abstractmethod
    def analyze_drops(self, audio_path: str, min_drop_time: float, min_tail_time: float) -> AudioDropAnalysis:
        pass
