from domain.ports.health_check import HealthCheckPort


class HealthCheckOrchestratorService:
    def __init__(self, checks: dict[str, HealthCheckPort]):
        self.checks = checks

    def run(self) -> list[tuple[str, str, str]]:
        results = []
        for name, check in self.checks.items():
            status = check.check_health()
            results.append((name, status.status, status.detail))
        return results
