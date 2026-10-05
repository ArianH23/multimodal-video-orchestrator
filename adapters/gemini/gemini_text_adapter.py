import json
from google import genai
from google.genai import types
from pydantic import BaseModel
from domain.ports.text_generation import TextGenerationPort
from domain.ports.health_check import HealthCheckPort
from domain.models.health_status import HealthStatus
from adapters.gemini.gemini_health import check_gemini_model_health


class _TopicEntry(BaseModel):
    topic: str
    image_prompts: list[str]
    font_rgb: list[int]


class _Quotes(BaseModel):
    text1: str
    text2: str


class _GeneratedContent(BaseModel):
    color: list[int]
    suggested_border_rgb: list[int]
    tiktok_description: str
    quotes: _Quotes
    image_name: str
    music: str


class GeminiTextAdapter(TextGenerationPort, HealthCheckPort):
    def __init__(self, api_key, model="gemini-3.1-pro-preview", temperature: float = 0.7, top_p: float = 0.9):
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.temperature = temperature
        self.top_p = top_p

    def check_health(self) -> HealthStatus:
        return check_gemini_model_health(self.client, self.model, required_action="generateContent")

    def generate_script_json(self, prompt):
        resp = self.client.models.generate_content(
            model=self.model,
            contents=types.Part.from_text(text=prompt),
            config=types.GenerateContentConfig(
                temperature=self.temperature,
                top_p=self.top_p,
                response_mime_type="application/json",
                response_schema=list[_TopicEntry],
            )
        )
        cleaned_response = json.loads(resp.text)
        cleaned_response = {item["topic"]: item for item in cleaned_response}
        return cleaned_response

    def generate_content_through_image(self, image, prompt):
        resp = self.client.models.generate_content(
            model=self.model,
            contents=[image, prompt],
            config=types.GenerateContentConfig(
                temperature=self.temperature,
                top_p=self.top_p,
                response_mime_type="application/json",
                response_schema=_GeneratedContent,
            )
        )
        return json.loads(resp.text)
