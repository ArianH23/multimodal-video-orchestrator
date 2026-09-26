from abc import ABC

from google import genai
from google.genai import types
from domain.ports.image_gen import ImageGeneratorPort
from domain.ports.health_check import HealthCheckPort
from domain.models.health_status import HealthStatus
from adapters.gemini.gemini_health import check_gemini_model_health


class GeminiImageAdapter(ImageGeneratorPort, HealthCheckPort, ABC):
    def __init__(self, api_key, model="gemini-3-pro-image"):
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.aspect_ratio = "9:16"  # @param ["1:1", "3:4", "4:3", "16:9", "9:16"]

    def check_health(self) -> HealthStatus:
        return check_gemini_model_health(self.client, self.model, required_action="generateContent")

    def create_image(self, prompt):
        resp = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                image_config=types.ImageConfig(aspect_ratio=self.aspect_ratio)
            )
        )

        for part in resp.candidates[0].content.parts:
            if part.inline_data:
                return part.inline_data.data

        raise ValueError("Gemini response did not contain an image part.")
