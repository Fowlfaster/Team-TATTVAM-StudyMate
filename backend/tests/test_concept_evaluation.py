import json
import unittest
from unittest.mock import Mock, patch

from tutor.concept_evaluation import (
    EvaluationGradeResponse,
    EvaluationQuestionResponse,
    generate_evaluation_question,
    grade_evaluation_answer,
)


def groq_response(payload: dict) -> Mock:
    response = Mock()
    response.choices = [Mock(message=Mock(content=json.dumps(payload)))]
    return response


class ConceptEvaluationTests(unittest.TestCase):
    @patch("tutor.concept_evaluation.groq_json")
    def test_question_rubric_maps_citations_and_has_three_to_six_ideas(self, groq_json_mock: Mock) -> None:
        groq_json_mock.return_value = EvaluationQuestionResponse.model_validate({
            "question": "Explain how fractions represent parts of a whole.",
            "rubric": [
                {"idea": "A fraction represents equal parts", "citation": 1},
                {"idea": "The numerator counts selected parts", "citation": 1},
                {"idea": "The denominator counts total parts", "citation": 2},
            ],
        })
        first_citation = {"n": 1, "file_name": "math.pdf", "source_type": "pdf", "page": 2, "snippet": "Parts"}
        second_citation = {"n": 2, "file_name": "math.pdf", "source_type": "pdf", "page": 3, "snippet": "Numerator"}

        result = generate_evaluation_question("Fractions", [
            {"text": "A fraction shows equal parts.", "citation": first_citation},
            {"text": "The denominator counts total parts.", "citation": second_citation},
        ])

        self.assertEqual(len(result["rubric"]), 3)
        self.assertEqual(result["rubric"][0]["citation"], first_citation)
        self.assertEqual(result["rubric"][2]["citation"], second_citation)

    @patch("tutor.concept_evaluation.groq_json")
    def test_grade_returns_covered_ideas_and_cited_misconceptions(self, groq_json_mock: Mock) -> None:
        groq_json_mock.return_value = EvaluationGradeResponse.model_validate({
            "coverage": 7,
            "accuracy": 8,
            "clarity": 6,
            "total_score": 7,
            "key_ideas_covered": [True, False, True],
            "misconceptions": [{"claim": "The denominator counts selected parts.", "correction": "The numerator counts selected parts.", "citation": 1}],
            "feedback": "You have the core idea; review what each number means.",
        })
        citation_a = {"n": 1, "file_name": "math.pdf", "source_type": "pdf", "page": 1, "snippet": "Numerator"}
        citation_b = {"n": 2, "file_name": "math.pdf", "source_type": "pdf", "page": 2, "snippet": "Denominator"}
        rubric = [
            {"idea": "Numerator counts selected parts", "citation": citation_a},
            {"idea": "Denominator counts all equal parts", "citation": citation_b},
            {"idea": "Fractions compare parts with the whole", "citation": citation_a},
        ]

        result = grade_evaluation_answer(
            "Explain fractions.",
            "A fraction shows selected parts compared with a whole, where the numerator counts selected parts and the denominator counts all equal parts.",
            rubric,
        )

        self.assertEqual([item["covered"] for item in result["key_ideas"]], [True, False, True])
        self.assertEqual(result["misconceptions"][0]["citation"], citation_a)
        self.assertEqual(result["total_score"], 7)
        self.assertEqual(groq_json_mock.call_args.kwargs["temperature"], 0)


if __name__ == "__main__":
    unittest.main()