import requests
from domain.ports.music_gen import MusicGeneratorPort


class SunoMusicAdapter(MusicGeneratorPort):
    def __init__(self, api_key, model):
        self.base_url = "https://api.sunoapi.org/api/v1/generate"
        self.api_key = api_key
        self.model = model

    def create_music(self, prompt: str):
        payload = {
            "customMode": False,
            "instrumental": True,
            "model": self.model,
            "callBackUrl": "https://api.example.com/callback",
            "prompt": prompt
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        response = requests.post(self.base_url, json=payload, headers=headers)
        response.raise_for_status()  # Good practice: fail fast on HTTP errors

        task_id = response.json().get('data', {}).get('taskId')
        if not task_id:
            raise ValueError("API did not return a taskId")

        return task_id

    def get_music(self, task_id: str):
        """Fetches the music and returns raw bytes for the storage adapter to handle."""
        url = f"{self.base_url}/record-info?taskId={task_id}"
        headers = {"Authorization": f"Bearer {self.api_key}"}

        response_data = requests.get(url, headers=headers)
        response_data.raise_for_status()

        data = response_data.json()

        try:
            track_1 = data['data']['response']['sunoData'][0]
            audio_url = track_1['sourceAudioUrl']
            audio_title = track_1['title']
        except (KeyError, IndexError):
            raise ValueError("Audio URL not found. The task might still be processing.")

        audio_response = requests.get(audio_url)
        audio_response.raise_for_status()

        return audio_title, audio_response.content
