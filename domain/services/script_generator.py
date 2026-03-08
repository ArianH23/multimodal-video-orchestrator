from domain.entities.script import Script

class ScriptGeneratorService:
    def __init__(self, text_port):
        self.text_port = text_port

    def generate(self, topic):
        raw = self.text_port.generate_script_json(topic)
        return Script(
            topic=raw["topic"],
            image_prompts=raw["image_prompts"],
            font_rgb=raw["font_rgb"],
        )
