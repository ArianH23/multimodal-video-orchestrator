from domain.ports.trend_searcher import TrendSearcherPort
from domain.ports.topic_repository import TopicRepositoryPort


class TrendOrchestratorService:
    def __init__(self, searcher: TrendSearcherPort, repository: TopicRepositoryPort):
        self.searcher = searcher
        self.repository = repository

    def generate_trending_video_topics(self, limit: int = 5) -> str:
        """Reads the internet (Tavily), then searches the DB."""
        print("\n=== MODE: AI TRENDING TAVILY SEARCH ===")
        report = self.searcher.fetch_current_trends()
        matched_topics = self.repository.find_similar_topics(query=report.summary, limit=limit)
        return self._format_output(matched_topics)

    def generate_random_video_topics(self, limit: int = 5) -> str:
        """Bypasses the internet, pulls random topics from DB."""
        print("\n=== MODE: RANDOM DATABASE ROULETTE ===")
        random_topics = self.repository.get_random_topics(limit=limit)
        return self._format_output(random_topics)

    def generate_explicit_video_topics(self, target_topics: list) -> str:
        """Bypasses the internet AND AI search, mathematically locking onto exact IDs."""
        print(f"\n=== MODE: EXPLICIT BATCH OVERRIDE ===")
        print(f"Targets: {target_topics}")

        matched_topics = self.repository.get_topics_by_ids(ids=target_topics)

        return self._format_output(matched_topics)

    def _format_output(self, topics) -> str:
        formatted_results = []
        for topic in topics:
            formatted_results.append(f"{topic.name}: {topic.color_rgb}")

        final_string = "\n".join(formatted_results)
        print("\n=== SELECTED TOPICS ===")
        print(final_string)
        return final_string
