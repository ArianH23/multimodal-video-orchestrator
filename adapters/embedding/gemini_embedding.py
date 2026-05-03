from chromadb import Documents, EmbeddingFunction, Embeddings
from google import genai


class ModernGeminiEmbeddingAdapter(EmbeddingFunction):
    def __init__(self, api_key: str, model_name: str = "gemini-embedding-2"):
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name

    def __call__(self, input: Documents) -> Embeddings:
        response = self.client.models.embed_content(
            model=self.model_name,
            contents=list(input)
        )

        return [embedding.values for embedding in response.embeddings]
