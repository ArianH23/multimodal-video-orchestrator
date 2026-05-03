import random
import chromadb
from domain.ports.topic_repository import TopicRepositoryPort
from domain.models.trends import MotivationalTopic
from typing import List


class ChromaTopicAdapter(TopicRepositoryPort):
    def __init__(self, storage_path: str, embedding_function):
        self.client = chromadb.PersistentClient(path=storage_path)
        self.collection = self.client.get_or_create_collection(
            name="motivational_topics",
            embedding_function=embedding_function
        )

    def find_similar_topics(self, query: str, limit: int = 5) -> List[MotivationalTopic]:
        results = self.collection.query(
            query_texts=[query],
            n_results=limit
        )

        matched_ids = results.get('ids', [[]])[0]
        matched_metadatas = results.get('metadatas', [[]])[0]

        topics = []
        for topic_id, metadata in zip(matched_ids, matched_metadatas):
            topics.append(MotivationalTopic(
                name=topic_id.capitalize(),  # Domain formatting rule applied here
                color_rgb=metadata.get('color', '[255, 255, 255]')
            ))

        return topics

    def get_random_topics(self, limit: int = 5) -> List[MotivationalTopic]:
        all_data = self.collection.get(include=[])
        all_ids = all_data['ids']

        if not all_ids:
            return []

        safe_limit = min(limit, len(all_ids))
        selected_ids = random.sample(all_ids, safe_limit)

        results = self.collection.get(
            ids=selected_ids,
            include=['metadatas']
        )

        topics = []
        for topic_id, metadata in zip(results['ids'], results['metadatas']):
            topics.append(MotivationalTopic(
                name=topic_id.capitalize(),
                color_rgb=metadata.get('color', '[255, 255, 255]')
            ))

        return topics

    def get_topics_by_ids(self, ids: List[str]) -> List[MotivationalTopic]:
        formatted_ids = [target.upper() for target in ids]

        results = self.collection.get(
            ids=formatted_ids,
            include=['metadatas']
        )

        topics = []
        for topic_id, metadata in zip(results['ids'], results['metadatas']):
            topics.append(MotivationalTopic(
                name=topic_id.capitalize(),
                color_rgb=metadata.get('color', '[255, 255, 255]')
            ))

        return topics
