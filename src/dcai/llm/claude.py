import os

from dcai.llm.base import LLMProvider, LLMResponse

DEFAULT_MODEL = "claude-haiku-4-5-20251001"


class ClaudeProvider(LLMProvider):
    """Wraps the anthropic SDK (direct, metered API billing). Reads
    ANTHROPIC_API_KEY from the environment only — never logged, never
    persisted to the DB. Far cheaper per call than ClaudeCodeProvider (a
    few hundred prompt tokens vs. Claude Code's ~10-17k token fixed
    overhead per invocation) since it sends only the tiny normalized
    Exercise prompt, nothing else."""

    name = "claude-api"

    def __init__(self, model: str = DEFAULT_MODEL):
        import anthropic  # optional dependency, imported lazily

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set.")
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def complete(self, system: str, user: str, max_tokens: int) -> LLMResponse:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(block.text for block in response.content if block.type == "text")
        return LLMResponse(
            text=text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            model=self._model,
        )
