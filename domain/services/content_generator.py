from domain.ports.text_generation import TextGenerationPort


class ContentGeneratorService:
    def __init__(self, text_port: TextGenerationPort):
        self.text_port = text_port

    def generate(self, prompt: str) -> dict:
        content = self.text_port.generate_script_json(prompt)
        return content

    def generate_from_image(self, image, prompt: str,) -> dict:
        content = self.text_port.generate_content_through_image(image, prompt)
        return content
