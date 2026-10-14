import unittest
import json
from unittest.mock import Mock, patch

from topic_extractor import TopicExtractionResponse, _request_topics, extract_topics


class TopicExtractorTests(unittest.TestCase):
    @patch("topic_extractor.groq_json")
    def test_topic_extractor_uses_shared_lenient_json_helper(self, groq_json_mock: Mock) -> None:
        groq_json_mock.return_value = TopicExtractionResponse.model_validate({
            "topics": [{"name": "Fractions", "summary": "Parts of a whole", "chunk_ids": "1-0"}],
        })

        result = _request_topics("Source prompt")

        self.assertEqual(result[0]["name"], "Fractions")
        self.assertEqual(result[0]["chunk_ids"], ["1-0"])
        groq_json_mock.assert_called_once()

    def test_merges_near_duplicates_and_assigns_each_chunk_once(self) -> None:
        chunks = [{"text": f"Material chunk {index}. " + ("Calculus fundamentals and number theory. " * 3)} for index in range(8)]
        proposals = [
            {"name": "Calculus", "summary": "Limits and derivatives", "chunk_ids": ["3-0", "3-1"]},
            {"name": "Calculus ", "summary": "Foundational calculus ideas", "chunk_ids": ["3-2", "3-3"]},
            {"name": "Derivatives", "summary": "Rates of change", "chunk_ids": ["3-3", "3-4"]},
            {"name": "Integrals", "summary": "Accumulated change", "chunk_ids": ["3-5"]},
            {"name": "Limits", "summary": "Behavior near a value", "chunk_ids": ["3-6"]},
            {"name": "Continuity", "summary": "Connected function behavior", "chunk_ids": ["3-7"]},
        ]
        with patch("topic_extractor._extract_batch", return_value=proposals):
            topics = extract_topics(3, chunks)

        assigned = [chunk_id for topic in topics for chunk_id in topic["chunk_ids"]]
        self.assertEqual(len(topics), 5)
        self.assertEqual(set(assigned), {f"3-{index}" for index in range(8)})
        self.assertEqual(len(assigned), len(set(assigned)))
        self.assertEqual(topics[0]["name"], "Calculus")

    def test_batches_long_sources_then_consolidates_topics(self) -> None:
        chunks = [{"text": f"Material chunk {index}"} for index in range(13)]
        final_topics = [
            {"name": f"Topic {index}", "summary": f"Summary {index}",
             "chunk_ids": [f"7-{chunk_id}" for chunk_id in chunk_ids]}
            for index, chunk_ids in enumerate(([0, 1, 2], [3, 4, 5], [6, 7, 8], [9, 10], [11, 12]))
        ]
        with patch("topic_extractor._extract_batch", return_value=[]) as extract_batch:
            with patch("topic_extractor._request_topics", return_value=final_topics) as consolidate:
                topics = extract_topics(7, chunks)

        self.assertEqual(extract_batch.call_count, 2)
        consolidate.assert_called_once()
        self.assertEqual(len(topics), 5)
        self.assertEqual(
            {chunk_id for topic in topics for chunk_id in topic["chunk_ids"]},
            {f"7-{index}" for index in range(13)},
        )

    def test_accepts_fewer_than_five_usable_topics(self) -> None:
        chunks = [{"text": f"Material chunk {index}. " + ("A useful topic summary with enough course text. " * 2)} for index in range(4)]
        proposals = [
            {"name": f"Topic {index}", "summary": f"Summary {index}", "chunk_ids": [f"4-{index}"]}
            for index in range(4)
        ]
        with patch("topic_extractor._extract_batch", return_value=proposals):
            with patch("topic_extractor._assign_chunks", return_value=[
                {"name": proposal["name"], "summary": proposal["summary"], "chunk_ids": proposal["chunk_ids"]}
                for proposal in proposals
            ]):
                topics = extract_topics(4, chunks)
        self.assertEqual(len(topics), 4)


if __name__ == "__main__":
    unittest.main()