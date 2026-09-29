"""Builds the smallest possible prompt from a normalized Exercise — never
raw HTML/screenshots — and deterministically validates the response
before it ever reaches the browser."""

import ast
import re

from dcai.llm.base import LLMProvider, LLMResponse
from dcai.models import Exercise

SYSTEM_PROMPT = (
    "You solve DataCamp coding exercises. Reply with ONLY the code that "
    "belongs in the editor — no explanation, no markdown fences. Any "
    "variable already used in the starter code (e.g. a preconfigured API "
    "client) is already defined in the sandbox — do not redefine, "
    "reimport, or reinstantiate it."
)

MCQ_SYSTEM_PROMPT = (
    "You solve DataCamp multiple-choice exercises. Reply with ONLY the "
    "exact text of the correct option, copied verbatim — no explanation, "
    "no option number, no extra words."
)

_FENCE_RE = re.compile(r"^```[\w]*\n|```$", re.MULTILINE)


def _build_prompt(exercise: Exercise, prior_error: str | None = None) -> str:
    parts = [f"Language: {exercise.language}", f"Instructions:\n{exercise.instructions}"]
    if exercise.starter_code:
        parts.append(f"Starter code:\n{exercise.starter_code}")
    if exercise.hints:
        parts.append("Hints:\n" + "\n".join(exercise.hints))
    if prior_error:
        parts.append(f"Previous attempt failed with:\n{prior_error}")
    return "\n\n".join(parts)


def strip_fences(text: str) -> str:
    return _FENCE_RE.sub("", text).strip()


def validate(code: str, language: str) -> bool:
    if language.lower() != "python":
        return bool(code.strip())
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False


def solve(provider: LLMProvider, exercise: Exercise, max_tokens: int = 1024) -> tuple[str, LLMResponse] | None:
    prompt = _build_prompt(exercise)
    response = provider.complete(SYSTEM_PROMPT, prompt, max_tokens)
    code = strip_fences(response.text)
    if not validate(code, exercise.language):
        return None
    return code, response


def _build_mcq_prompt(exercise: Exercise) -> str:
    options = exercise.context.get("options", [])
    numbered = "\n".join(f"{i + 1}. {opt}" for i, opt in enumerate(options))
    return f"Instructions:\n{exercise.instructions}\n\nOptions:\n{numbered}"


def solve_mcq(provider: LLMProvider, exercise: Exercise, max_tokens: int = 256) -> tuple[str, LLMResponse] | None:
    options = exercise.context.get("options", [])
    if not options:
        return None
    prompt = _build_mcq_prompt(exercise)
    response = provider.complete(MCQ_SYSTEM_PROMPT, prompt, max_tokens)
    answer = strip_fences(response.text).strip()
    if answer not in options:
        match = next((o for o in options if o.strip().lower() == answer.lower()), None)
        if match is None:
            return None
        answer = match
    return answer, response
