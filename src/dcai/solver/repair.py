"""Repair loop: on a failed submission, resend only the existing code and
the error message — never the original instructions, never a fresh
extraction — to keep repair attempts token-cheap."""

from dcai.llm.base import LLMProvider, LLMResponse
from dcai.solver.llm_solver import SYSTEM_PROMPT, strip_fences, validate

REPAIR_PROMPT_TEMPLATE = (
    "This code failed:\n{code}\n\nError:\n{error}\n\n"
    "Reply with ONLY the corrected code."
)


def repair(
    provider: LLMProvider, code: str, error: str, language: str, max_tokens: int = 1024
) -> tuple[str, LLMResponse] | None:
    prompt = REPAIR_PROMPT_TEMPLATE.format(code=code, error=error)
    response = provider.complete(SYSTEM_PROMPT, prompt, max_tokens)
    fixed = strip_fences(response.text)
    if not validate(fixed, language):
        return None
    return fixed, response
