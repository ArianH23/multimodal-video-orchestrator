from domain.ports.storage import StoragePort
from domain.ports.image_gen import ImageGeneratorPort


class ImageGenerationService:
    def __init__(self, image_port: ImageGeneratorPort, storage_port: StoragePort):
        self.image_port = image_port
        self.storage_port = storage_port

    def generate(self, prompt, path):
        img_bytes = self.image_port.create_image(prompt)
        saved_path = self.storage_port.save(img_bytes, path)
        return saved_path
