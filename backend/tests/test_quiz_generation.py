import unittest
from unittest.mock import patch

from quiz.generator import QuizQuestionsResponse, generate_questions


class QuizGenerationTests(unittest.TestCase):
    def test_generates_five_questions_for_only_the_requested_topic(self) -> None:
        chunks = [{
            "text": "Threads execute independently within a process.",
            "citation": {
                "n": 1,
                "file_name": "concurrency.pdf",
                "source_type": "pdf",
                "source_id": 7,
                "page": 3,
            },
        }]
        generated = QuizQuestionsResponse.model_validate({
            "questions": [{
                "question": f"Question {index} about threads?",
                "options": ["Address space", "A separate kernel", "A separate file", "A separate CPU"],
                "answer_index": 0,
                "explanation": "Threads in a process share its address space.",
            } for index in range(5)],
        })

        with patch("quiz.generator.retrieve_chunks", return_value=chunks) as retrieve:
            with patch("quiz.generator.groq_json", return_value=generated) as groq_json:
                result = generate_questions(
                    "Multithreading Model",
                    "medium",
                    user_id=4,
                    source_ids=[7],
                    subject_id=2,
                )

        self.assertEqual(len(result), 5)
        self.assertEqual(result[0]["difficulty"], "medium")
        self.assertEqual(result[0]["topic"], "Multithreading Model")
        self.assertEqual(result[0]["citation"], chunks[0]["citation"])
        self.assertEqual(result[0]["correct_index"], 0)
        self.assertEqual(retrieve.call_args.kwargs["topic"], "Multithreading Model")
        self.assertEqual(retrieve.call_args.kwargs["source_ids"], [7])
        self.assertEqual(groq_json.call_args.kwargs["max_attempts"], 2)
        self.assertTrue(groq_json.call_args.kwargs["log_raw_response"])
        self.assertIn('"questions"', groq_json.call_args.args[0])

    def test_rejects_incomplete_or_malformed_question_batches(self) -> None:
        with self.assertRaises(ValueError):
            QuizQuestionsResponse.model_validate({"questions": []})

        valid_question = {
            "question": "Question?",
            "options": ["A", "B", "C", "D"],
            "answer_index": 0,
            "explanation": "Because.",
        }
        with self.assertRaises(ValueError):
            QuizQuestionsResponse.model_validate({
                "questions": [valid_question] * 4 + [{**valid_question, "options": ["A"]}],
            })


if __name__ == "__main__":
    unittest.main()