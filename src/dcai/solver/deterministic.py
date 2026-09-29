"""Rule-based solver tier: MCQ answer-key lookups, regex-based code
patterns. Intentionally empty for the first vertical slice — a free
filter added once real usage shows what's worth hardcoding (Phase 2),
not built speculatively ahead of that evidence."""

from dcai.models import Exercise


def try_solve(exercise: Exercise) -> str | None:
    return None
