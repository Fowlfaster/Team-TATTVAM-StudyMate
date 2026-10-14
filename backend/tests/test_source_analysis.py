import json
import unittest
from unittest.mock import Mock, patch

from tutor.source_analysis import SourceOverview, analyze_source


class SourceAnalysisTests(unittest.TestCase):
    @patch("tutor.source_analysis.groq_json")
    @patch("tutor.source_analysis.generate_topic_explanation")
    def test_maps_every_topic_then_reduces_cited_overview(self, explain_topic: Mock, groq_json_mock: Mock) -> None:
        citations = [
            {"n": 1, "file_name": "course.pdf", "source_type": "pdf", "source_id": 7, "page": 1, "snippet": "Algebra passage"},
            {"n": 1, "file_name": "course.pdf", "source_type": "pdf", "source_id": 7, "page": 2, "snippet": "Geometry passage"},
        ]
        explain_topic.side_effect = [
            {"summary": "[[Algebra]] explains equations. {{It uses variables.}}", "key_points": ["Variables"], "example": "x = 2", "citations": [citations[0]], "glossary": [{"term": "Algebra", "definition": "Study of symbols"}]},
            {"summary": "[[Geometry]] studies shapes. {{Angles describe turns.}}", "key_points": ["Angles"], "example": "A triangle", "citations": [citations[1]], "glossary": [{"term": "Geometry", "definition": "Study of shapes"}]},
        ]
        overview = {
            "title": "Course foundations",
            "overview": "Algebra studies symbols. Variables represent values. Equations compare expressions. Geometry studies shapes. Angles describe turns. Triangles have three sides.",
            "learning_objectives": ["Describe variables", "Identify angle properties"],
            "summary": "The material introduces algebra and geometry.",
            "citations": [1, 2],
        }
        groq_json_mock.return_value = SourceOverview.model_validate(overview)
        topics = [{"id": 1, "name": "Algebra"}, {"id": 2, "name": "Geometry"}]
        chunks = {1: [{"text": "Algebra passage"}], 2: [{"text": "Geometry passage"}]}

        result = analyze_source("course.pdf", "beginner", topics, chunks)

        self.assertEqual(explain_topic.call_count, 2)
        self.assertEqual(len(result["sections"]), 2)
        self.assertEqual(result["sections"][1]["topic"], "Geometry")
        self.assertEqual(len(result["citations"]), 2)
        self.assertEqual({entry["term"] for entry in result["glossary"]}, {"Algebra", "Geometry"})
        self.assertEqual(result["title"], "Course foundations")


if __name__ == "__main__":
    unittest.main()
