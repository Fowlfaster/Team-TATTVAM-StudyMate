import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from ranking import level_for_score, score_topic


def attempt(correct: bool, difficulty: str, days_ago: int) -> SimpleNamespace:
    return SimpleNamespace(
        correct=correct,
        difficulty=difficulty,
        timestamp=datetime.now(timezone.utc) - timedelta(days=days_ago),
    )


class RankingTests(unittest.TestCase):
    def test_quiz_component_uses_difficulty_weights(self) -> None:
        result = score_topic([
            attempt(correct=True, difficulty="hard", days_ago=0),
            attempt(correct=False, difficulty="easy", days_ago=1),
        ], latest_evaluation_score=None)

        self.assertEqual(result["quiz_component"], 66.7)
        self.assertEqual(result["score"], 66.7)
        self.assertEqual(result["assessment_status"], "not enough data")

    def test_enough_quiz_attempts_without_evaluation_uses_quiz_only(self) -> None:
        result = score_topic([
            attempt(correct=True, difficulty="easy", days_ago=0),
            attempt(correct=True, difficulty="medium", days_ago=1),
            attempt(correct=False, difficulty="hard", days_ago=2),
        ], latest_evaluation_score=None)

        self.assertEqual(result["score"], result["quiz_component"])
        self.assertEqual(result["assessment_status"], "partially assessed")
        self.assertEqual(result["recommended_action"], "evaluate")

    def test_full_score_combines_quiz_evaluation_and_consistency(self) -> None:
        result = score_topic([
            attempt(correct=True, difficulty="easy", days_ago=0),
            attempt(correct=False, difficulty="medium", days_ago=1),
            attempt(correct=True, difficulty="hard", days_ago=2),
        ], latest_evaluation_score=8)

        self.assertEqual(result["consistency"], 50.0)
        self.assertEqual(result["score"], 70.3)
        self.assertEqual(result["assessment_status"], "assessed")

    def test_consistency_compares_recent_five_to_earlier_attempts(self) -> None:
        attempts = [attempt(correct=True, difficulty="easy", days_ago=day) for day in range(5)]
        attempts.append(attempt(correct=False, difficulty="easy", days_ago=5))

        result = score_topic(attempts, latest_evaluation_score=10)

        self.assertEqual(result["consistency"], 0.0)

    def test_level_boundaries(self) -> None:
        self.assertEqual(level_for_score(39), "Beginner")
        self.assertEqual(level_for_score(40), "Developing")
        self.assertEqual(level_for_score(70), "Proficient")
        self.assertEqual(level_for_score(85), "Mastered")


if __name__ == "__main__":
    unittest.main()