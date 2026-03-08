from domain.entities.script import Script


class ImagePipelineService:
    def __init__(self, image_port, storage_port):
        self.image_port = image_port
        self.storage_port = storage_port

    def generate(self, spec):
        img_bytes = self.image_port.create_image(spec.prompt)
        saved_path = self.storage_port.save_image(img_bytes, spec.name)
        return saved_path
