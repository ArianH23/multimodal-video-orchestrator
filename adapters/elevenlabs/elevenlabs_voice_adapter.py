# adapters/elevenlabs/elevenlabs_voice_adapter.py
import requests
from domain.ports.voice_gen import VoiceGenerationPort


class ElevenLabsVoiceAdapter(VoiceGenerationPort):
    def __init__(self, api_key: str, voice_id: str):
        self.api_key = api_key
        self.voice_id = voice_id
        self.base_url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}"

    def text_to_speech(self, text: str, voice_settings: dict) -> bytes:
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json; charset=utf-8",
            "xi-api-key": self.api_key
        }

        payload = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": voice_settings
        }

        response = requests.post(self.base_url, json=payload, headers=headers)
        response.raise_for_status()

        return response.content