# adapters/search/tavily_adapter.py
from tavily import TavilyClient
from domain.ports.trend_searcher import TrendSearcherPort
from domain.models.trends import TrendReport, TrendSource


class TavilyTrendAdapter(TrendSearcherPort):
    def __init__(self, api_key: str):
        self.client = TavilyClient(api_key=api_key)

    def fetch_current_trends(self, region: str = "España") -> TrendReport:
        print(f"Querying Tavily for current trends in {region}...")

        query = (
            f"Analiza las noticias de hoy y los temas de tendencia en {region} sobre "
            "desarrollo personal, salud mental y motivación. "
            "No escribas un informe completo. En su lugar, proporciona una única oración "
            "muy concentrada que describa la principal lucha emocional o necesidad "
            "psicológica que expresan las personas hoy."
        )

        response = self.client.search(
            query=query,
            search_depth="advanced",
            topic="news",
            max_results=5,
            include_answer=True,
            include_domains=["elpais.com", "elmundo.es", "lavanguardia.com", "abc.es", "rtve.es"]
        )

        summary = response.get("answer", "No answer generated.")
        raw_sources = response.get("results", [])

        sources = [TrendSource(title=s['title'], url=s['url']) for s in raw_sources]

        return TrendReport(summary=summary, sources=sources)