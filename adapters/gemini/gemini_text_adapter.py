import json
from google import genai
from google.genai import types
from domain.ports.text_generation import TextGenerationPort
from domain.ports.health_check import HealthCheckPort
from domain.models.health_status import HealthStatus
from adapters.gemini.gemini_health import check_gemini_model_health


class GeminiTextAdapter(TextGenerationPort, HealthCheckPort):
    def __init__(self, api_key, model="gemini-3.1-pro-preview"):
        self.client = genai.Client(api_key=api_key)
        self.model = model

    def check_health(self) -> HealthStatus:
        return check_gemini_model_health(self.client, self.model, required_action="generateContent")

    def generate_script_json(self, prompt):
        resp = self.client.models.generate_content(
            model=self.model,
            contents=types.Part.from_text(text=prompt),
            config=types.GenerateContentConfig(
                temperature=0.7,
                top_p=0.9
            )
        )
        cleaned_response = (
            resp.text
            .replace("```python", "")
            .replace("```", "")
        )
        cleaned_response = eval(cleaned_response)
        cleaned_response = {item["topic"]: item for item in cleaned_response}
        return cleaned_response

    def generate_content_through_image(self, image, prompt):
        resp = self.client.models.generate_content(
            model=self.model,
            contents=[image, prompt],
            config=types.GenerateContentConfig(
                temperature=0.7,
                top_p=0.9
            )
        )
        cleaned_response = (
            resp.text
            .replace("```json", "")
            .replace("```", "")
        )
        cleaned_response = eval(cleaned_response)

        return cleaned_response
