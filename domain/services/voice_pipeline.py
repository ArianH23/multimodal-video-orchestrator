# domain/services/voice_pipeline.py
import random
from domain.ports.voice_gen import VoiceGenerationPort
from domain.ports.storage import StoragePort


class VoicePipelineService:
    def __init__(self, voice_port: VoiceGenerationPort, storage: StoragePort):
        self.voice_port = voice_port
        self.storage = storage

    def _clean_text(self, text: str) -> str:
        replacements = {
            'Ã¡': 'á', 'Ã©': 'é', 'Ã\xad': 'í',
            'Ã³': 'ó', 'Ãº': 'ú', 'Â¿': '¿', 'Ã±': 'ñ'
        }
        for k, v in replacements.items():
            text = text.replace(k, v)
        return text

    def _ensure_period(self, text: str) -> str:
        return text if text.endswith('.') else text + '.'

    def _reflective_tone(self) -> dict:
        return {
            "speed": round((random.uniform(0.45, 0.5) * 0.5) + 0.7, 2),
            "stability": 0.4,
            "similarity_boost": round(random.uniform(0.8, 0.85), 2),
            "style": round(random.uniform(0.35, 0.45), 2),
            "use_speaker_boost": False
        }

    def _emotional_resolution(self) -> dict:
        return {
            "speed": round((random.uniform(0.55, 0.6) * 0.5) + 0.7, 2),
            "stability": random.uniform(0.65, 0.7),
            "similarity_boost": round(random.uniform(0.85, 0.9), 2),
            "style": round(random.uniform(0.6, 0.7), 2),
            "use_speaker_boost": True
        }

    def generate_voices(self, title: str, quotes: dict) -> list[str]:

        text1 = self._ensure_period(self._clean_text(quotes["text1"]))
        text2 = self._ensure_period(self._clean_text(quotes["text2"]))

        print("Generating Voice 1 (Reflective)...")
        audio1_bytes = self.voice_port.text_to_speech(text1, self._reflective_tone())

        print("Generating Voice 2 (Emotional)...")
        audio2_bytes = self.voice_port.text_to_speech(text2, self._emotional_resolution())

        path1 = self.storage.save(f"data/voices/{title}/voice1.mp3", audio1_bytes)
        path2 = self.storage.save(f"data/voices/{title}/voice2.mp3", audio2_bytes)

        print(f"Voices successfully saved to {path1} and {path2}")
        return [path1, path2]
