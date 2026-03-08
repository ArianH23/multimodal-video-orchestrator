import random

class VoicePipelineService:
    def __init__(self, voice_port, storage_port):
        self.voice_port = voice_port
        self.storage = storage_port

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

    def _reflective_tone(self):
        return {
            "speed": round((random.uniform(0.46, 0.47) * 0.5) + 0.7, 2),
            "stability": 0.4,
            "similarity_boost": round(random.uniform(0.8, 0.85), 2),
            "style": round(random.uniform(0.35, 0.45), 2),
            "use_speaker_boost": False
        }

    def _emotional_resolution(self):
        return {
            "speed": round((random.uniform(0.56, 0.57) * 0.5) + 0.7, 2),
            "stability": random.uniform(0.65, 0.7),
            "similarity_boost": round(random.uniform(0.85, 0.9), 2),
            "style": round(random.uniform(0.6, 0.7), 2),
            "use_speaker_boost": True
        }

    def generate(self, title: str, quotes: dict):
        text1 = self._ensure_period(self._clean_text(quotes["text1"]))
        text2 = self._ensure_period(self._clean_text(quotes["text2"]))

        audio1 = self.voice_port.text_to_speech(text1, self._reflective_tone())
        audio2 = self.voice_port.text_to_speech(text2, self._emotional_resolution())

        self.storage.save_audio(audio1, f"7.voices/{title}/voice1.mp3")
        self.storage.save_audio(audio2, f"7.voices/{title}/voice2.mp3")