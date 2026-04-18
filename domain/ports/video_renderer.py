from abc import ABC, abstractmethod
from domain.models.video_spec import VideoSpecification


class VideoRendererPort(ABC):
    @abstractmethod
    def render_video(self, spec: VideoSpecification) -> str:
        pass
