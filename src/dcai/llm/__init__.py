from dcai.llm.base import LLMProvider

_PROVIDERS = {
    "claude-code": lambda: __import__("dcai.llm.claude_code", fromlist=["ClaudeCodeProvider"]).ClaudeCodeProvider(),
    "claude-api": lambda: __import__("dcai.llm.claude", fromlist=["ClaudeProvider"]).ClaudeProvider(),
}


def get_provider(name: str) -> LLMProvider:
    factory = _PROVIDERS.get(name)
    if factory is None:
        raise ValueError(f"Unknown LLM provider: {name!r} (known: {sorted(_PROVIDERS)})")
    return factory()
