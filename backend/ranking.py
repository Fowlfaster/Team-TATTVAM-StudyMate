from collections import defaultdict
from typing import Any

from sqlmodel import Session, select

from db import ConceptEvaluation, QuizAttempt, Topic


DIFFICULTY_WEIGHTS = {"easy": 1.0, "medium": 1.5, "hard": 2.0}
RECENT_ATTEMPT_LIMIT = 20


def level_for_score(score: float) -> str:
    if score < 40:
        return "Beginner"
    if score < 70:
        return "Developing"
    if score < 85:
        return "Proficient"
    return "Mastered"


def score_topic(
    attempts: list[Any],
    latest_evaluation_score: float | None,
) -> dict[str, Any]:
    ordered_attempts = sorted(attempts, key=lambda item: item.timestamp, reverse=True)
    recent_attempts = ordered_attempts[:RECENT_ATTEMPT_LIMIT]
    weight_total = sum(DIFFICULTY_WEIGHTS.get(item.difficulty, 1.0) for item in recent_attempts)
    quiz_component = None
    if weight_total:
        quiz_component = 100 * sum(
            DIFFICULTY_WEIGHTS.get(item.difficulty, 1.0) * int(item.correct)
            for item in recent_attempts
        ) / weight_total

    consistency = None
    if ordered_attempts:
        last_five = ordered_attempts[:5]
        earlier = ordered_attempts[5:]
        if earlier:
            recent_accuracy = sum(int(item.correct) for item in last_five) / len(last_five)
            earlier_accuracy = sum(int(item.correct) for item in earlier) / len(earlier)
            consistency = 100 * (1 - abs(recent_accuracy - earlier_accuracy))
        else:
            consistency = 50.0

    evaluation_component = (
        None if latest_evaluation_score is None
        else min(100.0, max(0.0, latest_evaluation_score * 10))
    )
    attempt_count = len(ordered_attempts)
    if evaluation_component is None:
        score = quiz_component if quiz_component is not None else 0.0
        assessment_status = "not enough data" if attempt_count < 3 else "partially assessed"
    elif quiz_component is None:
        score = evaluation_component
        assessment_status = "partially assessed"
    else:
        score = 0.5 * quiz_component + 0.4 * evaluation_component + 0.1 * (consistency or 50.0)
        assessment_status = "assessed" if attempt_count >= 3 else "partially assessed"

    score = round(min(100.0, max(0.0, score)), 1)
    if evaluation_component is None or attempt_count == 0:
        recommended_action = "evaluate"
    elif score < 40:
        recommended_action = "explain"
    else:
        recommended_action = "quiz"

    return {
        "score": score,
        "level": level_for_score(score),
        "assessment_status": assessment_status,
        "quiz_component": None if quiz_component is None else round(quiz_component, 1),
        "evaluation_component": None if evaluation_component is None else round(evaluation_component, 1),
        "consistency": None if consistency is None else round(consistency, 1),
        "attempt_count": attempt_count,
        "recommended_action": recommended_action,
    }


def rank_topics(
    session: Session,
    user_id: int,
    source_ids: list[int] | None = None,
    topic_names: list[str] | None = None,
    subject_id: int | None = None,
) -> dict[str, Any]:
    topic_statement = select(Topic).where(Topic.user_id == user_id)
    if subject_id is not None:
        topic_statement = topic_statement.where(Topic.subject_id == subject_id)
    if source_ids:
        topic_statement = topic_statement.where(Topic.source_id.in_(source_ids))
    if topic_names:
        topic_statement = topic_statement.where(Topic.name.in_(topic_names))
    topic_rows = session.exec(topic_statement.order_by(Topic.name)).all()

    grouped_topics: dict[str, list[Topic]] = defaultdict(list)
    for topic in topic_rows:
        grouped_topics[topic.name].append(topic)
    if not grouped_topics:
        return {"overall_score": None, "assessed_topics": 0, "topics": []}

    topic_names = list(grouped_topics)
    attempts = session.exec(
        select(QuizAttempt).where(
            QuizAttempt.user_id == user_id,
            QuizAttempt.topic.in_(topic_names),
        )
    ).all()
    evaluations = session.exec(
        select(ConceptEvaluation).where(
            ConceptEvaluation.user_id == user_id,
            ConceptEvaluation.topic_id.in_(
                [topic.id for topic in topic_rows if topic.id is not None]
            ),
            ConceptEvaluation.total_score.is_not(None),
        )
    ).all()

    ranked = []
    for topic_name, records in grouped_topics.items():
        record_source_ids = sorted({int(record.source_id) for record in records})
        record_topic_ids = {int(record.id) for record in records if record.id is not None}
        topic_attempts = []
        for attempt in attempts:
            if attempt.topic != topic_name:
                continue
            recorded_sources = set(attempt.source_ids or [])
            if source_ids:
                if not recorded_sources or not recorded_sources.intersection(record_source_ids):
                    continue
            topic_attempts.append(attempt)

        topic_evaluations = [
            evaluation for evaluation in evaluations if evaluation.topic_id in record_topic_ids
        ]
        latest_evaluation = max(
            topic_evaluations,
            key=lambda item: (item.created_at, item.id or 0),
            default=None,
        )
        score_data = score_topic(
            topic_attempts,
            latest_evaluation.total_score if latest_evaluation is not None else None,
        )
        ranked.append({
            "topic": topic_name,
            "source_ids": record_source_ids,
            "topic_ids": sorted(record_topic_ids),
            **score_data,
        })

    ranked.sort(key=lambda item: (item["score"], item["topic"].casefold()))
    assessed_scores = [
        item["score"] for item in ranked
        if item["assessment_status"] != "not enough data"
    ]
    overall_score = round(sum(assessed_scores) / len(assessed_scores), 1) if assessed_scores else None
    return {
        "overall_score": overall_score,
        "assessed_topics": len(assessed_scores),
        "topics": ranked,
    }