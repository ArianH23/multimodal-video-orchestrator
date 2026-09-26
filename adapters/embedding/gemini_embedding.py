from chromadb import Documents, EmbeddingFunction, Embeddings
from google import genai

from domain.ports.health_check import HealthCheckPort
from domain.models.health_status import HealthStatus
from adapters.gemini.gemini_health import check_gemini_model_health


class ModernGeminiEmbeddingAdapter(EmbeddingFunction, HealthCheckPort):
    def __init__(self, api_key: str, model_name: str = "gemini-embedding-2"):
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name

    def check_health(self) -> HealthStatus:
        return check_gemini_model_health(self.client, self.model_name, required_action="embedContent")

    def __call__(self, input: Documents) -> Embeddings:
        response = self.client.models.embed_content(
            model=self.model_name,
            contents=list(input)
        )

        return [embedding.values for embedding in response.embeddings]
