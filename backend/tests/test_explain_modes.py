import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tutor.explain_modes import (
    ElaborationResponse,
    SimpleMap,
    SimpleReduce,
    elaborate_further,
    explain_simply,
)
import main


class ExplainModesTests(unittest.TestCase):
    def test_simple_explanation_requests_complete_html_and_key_points(self) -> None:
        responses = [
            SimpleMap.model_validate({
                "simple_explanation": "A process contains one or more threads.",
                "everyday_analogy": "A kitchen can have several cooks.",
            }),
            SimpleReduce.model_validate({
                "title": "Threads",
                "big_picture": (
                    "<h3>How threads work</h3><p>"
                    + "<mark>Important sentence.</mark> " * 3
                    + "grounded " * 120
                    + "</p>"
                ),
                "key_points": ["Threads share process resources.", "Each thread has its own stack.", "The scheduler runs threads."],
            }),
        ]
        with patch("tutor.explain_modes.groq_json", side_effect=responses) as groq_json:
            result = explain_simply("Operating Systems", [{
                "id": 4,
                "source_id": 2,
                "name": "Thread Model",
                "summary": "How threads execute in a process.",
                "chunks": [{
                    "text": "Threads share the process address space.",
                    "citation": {
                        "n": 1,
                        "source_id": 2,
                        "file_name": "threads.pdf",
                        "source_type": "pdf",
                        "page": 2,
                        "snippet": "Threads share the process address space.",
                    },
                }],
            }])

        reduce_call = groq_json.call_args_list[-1]
        self.assertIn("100 and 150 words", reduce_call.args[1])
        self.assertIn("<mark>", reduce_call.args[1])
        self.assertEqual(reduce_call.kwargs["max_tokens"], 2000)
        word_count = len(result["big_picture"].split())
        self.assertGreaterEqual(word_count, 100)
        self.assertLessEqual(word_count, 150)
        self.assertEqual(result["big_picture"].count("<mark>"), 3)
        self.assertTrue(result["big_picture"].startswith("<h3>"))
        self.assertEqual(len(result["key_points"]), 3)

    def test_elaboration_receives_previous_text_and_original_document(self) -> None:
        response = ElaborationResponse.model_validate({
            "html": "<h3>Why sharing memory matters</h3><p>A new example.</p>",
            "key_points": ["A new takeaway."],
        })
        topic = {
            "id": 4,
            "source_id": 2,
            "name": "Thread Model",
            "summary": "How threads execute in a process.",
            "chunks": [{
                "text": "Threads share the process address space.",
                "citation": {
                    "n": 1,
                    "source_id": 2,
                    "file_name": "threads.pdf",
                    "source_type": "pdf",
                    "page": 2,
                    "snippet": "Threads share the process address space.",
                },
            }],
        }
        with patch("tutor.explain_modes.groq_json", return_value=response) as groq_json:
            result = elaborate_further(
                "Operating Systems",
                [topic],
                "<p>Threads share an address space.</p>",
                depth=2,
                focus="address-space sharing",
            )

        prompt = groq_json.call_args.args[1]
        self.assertIn("Threads share an address space", prompt)
        self.assertIn("Threads share the process address space", prompt)
        self.assertIn("level 2 of 3", prompt)
        self.assertEqual(groq_json.call_args.kwargs["max_tokens"], 2000)
        self.assertTrue(result["html"].startswith("<h3>"))

    def test_elaboration_rejects_depth_above_three(self) -> None:
        with self.assertRaises(ValueError):
            elaborate_further("Course", [{"chunks": []}], "Previous", depth=4)

    def test_elaboration_endpoint_scopes_to_selected_topic(self) -> None:
        request = main.ElaborateRequest(
            subject_id=8,
            source_id=12,
            topic_id=17,
            previous_explanation="Previously explained details.",
            depth=2,
            focus="why threads share memory",
        )
        topic = {"id": 17, "name": "Threads", "chunks": []}
        response = {"html": "<p>Deeper detail.</p>", "key_points": ["New point"]}
        with patch("main._load_subject_topics", return_value=("Operating Systems", [topic])) as load_topics:
            with patch("main.elaborate_further", return_value=response) as elaborate:
                result = main.elaborate_explanation(request, user=SimpleNamespace(id=4))

        load_topics.assert_called_once_with(8, 12, 4, [17])
        elaborate.assert_called_once_with(
            "Operating Systems",
            [topic],
            "Previously explained details.",
            2,
            "why threads share memory",
        )
        self.assertEqual(result["depth"], 2)


if __name__ == "__main__":
    unittest.main()
