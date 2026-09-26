from domain.models.health_status import HealthStatus


def check_gemini_model_health(client, model: str, required_action: str) -> HealthStatus:
    if not model:
        return HealthStatus("SKIPPED", "no model configured")

    try:
        info = client.models.get(model=model)
        if required_action not in (info.supported_actions or []):
            return HealthStatus(
                "FAIL",
                f"{model} exists but does not support '{required_action}' "
                f"(supports: {info.supported_actions})"
            )
        return HealthStatus("OK", f"{model} available ({info.name})")
    except Exception as e:
        return HealthStatus("FAIL", f"{model}: {e}")
