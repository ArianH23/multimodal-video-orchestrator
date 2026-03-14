import time
from domain.ports.music_gen import MusicGeneratorPort
from domain.ports.storage import StoragePort


class MusicGenerationService:
    def __init__(self, music_api: MusicGeneratorPort, storage: StoragePort):
        # We inject the interfaces, not the concrete implementations!
        self.music_api = music_api
        self.storage = storage

    def generate_and_save_track(self, prompt: str) -> str:
        """
        Orchestrates the creation, retrieval, and storage of a new track.
        """
        task_id = self.music_api.create_music(prompt)
        print(f"Task started: {task_id}. Waiting for completion...")

        audio_bytes = None
        while True:
            try:
                song_title, audio_bytes = self.music_api.get_music(task_id)
                break  # If we got the bytes, break the loop
            except ValueError as e:
                # Our adapter raises a ValueError if it's still processing
                print("Still processing, waiting 10 seconds...")
                time.sleep(10)

        filename = f"data/music/{song_title}_{task_id}.mp3"
        saved_path = self.storage.save(filename, audio_bytes)

        print(f"Track successfully generated and saved to {saved_path}")

        return saved_path