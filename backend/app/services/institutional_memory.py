from collections import Counter, defaultdict

from app.services.database import list_lessons_learned, list_outcome_dashboard_data, save_lesson_learned


def generate_lessons_learned(min_count: int = 2) -> dict:
    data = list_outcome_dashboard_data()
    misses = [row for row in data.get("opportunity_outcomes", []) if row.get("hit_miss_label") == "miss"]
    saved: list[dict] = []
    asset_counter = Counter(row.get("asset_class", "unknown") for row in misses)
    for asset_class, count in asset_counter.items():
        if count >= min_count:
            lesson = {
                "lesson_type": "asset_class_weakness",
                "pattern": f"Repeated misses in {asset_class}",
                "evidence": [row.get("idea_id") for row in misses if row.get("asset_class") == asset_class][:10],
                "severity": min(10.0, 4.0 + count),
                "recommendation": f"Require stronger confirming evidence before approving new {asset_class} hypotheses.",
            }
            save_lesson_learned(lesson)
            saved.append(lesson)
    conviction_misses = [row for row in misses if (row.get("conviction_score") or 0) >= 7]
    if len(conviction_misses) >= min_count:
        lesson = {
            "lesson_type": "overconfidence",
            "pattern": "High-conviction ideas missed realized outcomes",
            "evidence": [row.get("idea_id") for row in conviction_misses[:10]],
            "severity": min(10.0, 5.0 + len(conviction_misses) / 2),
            "recommendation": "Add explicit disconfirming evidence checks for conviction scores above 7.",
        }
        save_lesson_learned(lesson)
        saved.append(lesson)
    missing_evidence = [row for row in misses if not row.get("notes")]
    if len(missing_evidence) >= min_count:
        lesson = {
            "lesson_type": "missing_evidence",
            "pattern": "Failed ideas lacked detailed outcome notes",
            "evidence": [row.get("idea_id") for row in missing_evidence[:10]],
            "severity": 6.0,
            "recommendation": "Require richer post-mortem notes before using misses as negative examples.",
        }
        save_lesson_learned(lesson)
        saved.append(lesson)
    return {"created": len(saved), "lessons": saved}


def retrieve_relevant_lessons(query: str, limit: int = 5) -> list[dict]:
    terms = {term.lower() for term in query.split() if len(term) > 3}
    scored = []
    for lesson in list_lessons_learned(100):
        haystack = f"{lesson.get('lesson_type')} {lesson.get('pattern')} {lesson.get('recommendation')}".lower()
        score = sum(1 for term in terms if term in haystack)
        if score:
            scored.append((score, lesson))
    return [lesson for _, lesson in sorted(scored, key=lambda item: item[0], reverse=True)[:limit]]


def dashboard_lessons_summary() -> dict:
    lessons = list_lessons_learned(100)
    by_type: defaultdict[str, int] = defaultdict(int)
    for lesson in lessons:
        by_type[lesson.get("lesson_type", "unknown")] += 1
    return {"lessons": lessons, "count_by_type": dict(by_type)}
