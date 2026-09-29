"""Rule-based exercise type classification from DOM markers only.
Never an LLM call — deterministic logic handles anything it can."""

from dcai.adapters import selectors
from dcai.adapters.base import BrowserAdapter
from dcai.models import ExerciseType


def classify(adapter: BrowserAdapter) -> ExerciseType:
    if _js_bool(adapter, selectors.JS_HAS_MONACO_EDITOR):
        language = adapter.eval_text(selectors.JS_GET_EDITOR_LANGUAGE) or ""
        return ExerciseType.SQL_CODING if language.lower() == "sql" else ExerciseType.CODING
    if _js_bool(adapter, selectors.JS_HAS_MCQ_OPTIONS):
        return ExerciseType.MCQ
    # Live-verified (2026-09-29): course-intro/lesson videos have neither
    # Monaco nor MCQ options, only a "Got It!" continue button — previously
    # these fell through to MCQ by default and crashed the solver trying to
    # write to a nonexistent Monaco editor.
    if _js_bool(adapter, selectors.JS_HAS_GOT_IT_BUTTON):
        return ExerciseType.VIDEO
    return ExerciseType.THEORY


def _js_bool(adapter: BrowserAdapter, js_expression: str) -> bool:
    # eval_text only returns strings; booleans need their own path in the
    # adapter. Kept local and narrow rather than widening BrowserAdapter's
    # interface for one extra return type.
    return bool(adapter.eval_text(f"String({js_expression})") == "true")
