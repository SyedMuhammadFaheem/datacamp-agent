import hashlib
import json
import re

from dcai.adapters import selectors
from dcai.adapters.base import BrowserAdapter
from dcai.models import Exercise
from dcai.normalize.classify import classify


def _normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def instructions_hash(instructions: str, exercise_type: str, language: str) -> str:
    key = _normalize_ws(instructions) + exercise_type + language
    return hashlib.sha256(key.encode()).hexdigest()


def normalize(adapter: BrowserAdapter, exercise_id: str) -> Exercise:
    """Extract the current exercise state deterministically. Identical DOM
    state produces a byte-identical Exercise. Only JS text-getters are used
    — no HTML or screenshots ever pass through this function."""
    exercise_type = classify(adapter)
    raw_instructions = adapter.eval_text(selectors.JS_GET_INSTRUCTIONS) or ""
    instructions = _normalize_ws(raw_instructions)
    language = adapter.eval_text(selectors.JS_GET_EDITOR_LANGUAGE) or "python"

    starter_code = None
    current_code = None
    if exercise_type.value in ("coding", "sql_coding"):
        current_code = adapter.get_editor_content()
        starter_code = current_code

    context: dict = {}
    if exercise_type.value == "mcq":
        raw_options = adapter.eval_text(selectors.JS_GET_MCQ_OPTIONS) or "[]"
        context["options"] = json.loads(raw_options)

    return Exercise(
        id=exercise_id,
        type=exercise_type,
        language=language,
        instructions=instructions,
        starter_code=starter_code,
        current_code=current_code,
        context=context,
        hints=[],
        error_output=None,
    )
