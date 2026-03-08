from abc import ABC, abstractmethod

class VoiceGenerationPort(ABC):

    @abstractmethod
    def text_to_speech(self, text: str, voice_settings: dict) -> bytes:
        pass
