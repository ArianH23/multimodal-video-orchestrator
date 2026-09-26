import os
from dotenv import load_dotenv

from adapters.gemini.gemini_text_adapter import GeminiTextAdapter
from adapters.gemini.gemini_image_adapter import GeminiImageAdapter
from adapters.embedding.gemini_embedding import ModernGeminiEmbeddingAdapter
from adapters.elevenlabs.elevenlabs_voice_adapter import ElevenLabsVoiceAdapter
from adapters.sunoapi.suno_music_adapter import SunoMusicAdapter
from adapters.search.tavily_adapter import TavilyTrendAdapter
from domain.services.health_check_orchestrator import HealthCheckOrchestratorService

load_dotenv()


def build_checks(model_overrides: dict = None) -> dict:
    model_overrides = model_overrides or {}

    gemini_key = os.getenv("API_KEY")
    llm_model = model_overrides.get("LLM_MODEL", os.getenv("LLM_MODEL"))
    image_model = model_overrides.get("IMAGE_MODEL", os.getenv("IMAGE_MODEL"))
    embedding_model = model_overrides.get("EMBEDDING_MODEL", os.getenv("EMBEDDING_MODEL"))
    suno_model = model_overrides.get("SUNO_MODEL", os.getenv("SUNO_MODEL"))

    return {
        "LLM_MODEL": GeminiTextAdapter(gemini_key, llm_model),
        "IMAGE_MODEL": GeminiImageAdapter(gemini_key, image_model),
        "EMBEDDING_MODEL": ModernGeminiEmbeddingAdapter(gemini_key, embedding_model),
        "ElevenLabs": ElevenLabsVoiceAdapter(os.getenv("XI_API_KEY"), os.getenv("SPANISH_VOICE_ID")),
        "Suno": SunoMusicAdapter(os.getenv("SUNO_API_KEY"), suno_model),
        "Tavily": TavilyTrendAdapter(os.getenv("TAVILY_API_KEY")),
    }


def run_checks(model_overrides: dict = None) -> list[tuple[str, str, str]]:
    checks = build_checks(model_overrides)
    return HealthCheckOrchestratorService(checks).run()


def main():
    results = run_checks()
    width = max(len(name) for name, _, _ in results)
    for name, status, detail in results:
        print(f"{name.ljust(width)}  [{status}]  {detail}")


if __name__ == "__main__":
    main()
