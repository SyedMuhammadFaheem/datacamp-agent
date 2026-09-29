"""Uses the locally installed `claude` CLI in headless mode, authenticated
via the user's existing Claude Pro/Max subscription login rather than a
separate ANTHROPIC_API_KEY — usage counts against the subscription, not a
metered bill.

Deliberate tradeoff, not an oversight: measured against a real invocation,
each call carries ~10,000-17,500 tokens of fixed Claude Code overhead
(its own system prompt + full tool schemas, sent even with every tool
disallowed) that did NOT hit Anthropic's prompt cache on a repeat call in
testing — versus a few hundred prompt tokens for ClaudeProvider's direct
API call. This is the default provider anyway per explicit user choice
(avoiding a separate API bill outweighs the extra per-call token cost for
this user) — see README.md's provider comparison before assuming this is
the right default elsewhere.
"""

import json
import subprocess
import tempfile

from dcai.llm.base import LLMProvider, LLMResponse

DEFAULT_MODEL = "haiku"

# dcai only ever wants a text/code completion from this call, never an
# agentic action — block every tool so the subprocess can't do anything
# but respond.
_DISALLOWED_TOOLS = "Bash,Edit,Write,Read,Agent,WebFetch,WebSearch,NotebookEdit,Glob,Grep"


class ClaudeCodeProvider(LLMProvider):
    name = "claude-code"

    def __init__(self, model: str = DEFAULT_MODEL):
        self._model = model

    def complete(self, system: str, user: str, max_tokens: int) -> LLMResponse:
        cmd = [
            "claude", "-p", user,
            "--output-format", "json",
            "--system-prompt", system,
            "--model", self._model,
            "--disallowedTools", _DISALLOWED_TOOLS,
            "--strict-mcp-config",
        ]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                # Run from a neutral directory so no project's CLAUDE.md
                # or MCP config gets auto-discovered and added to the
                # (already large) fixed overhead.
                cwd=tempfile.gettempdir(),
            )
        except FileNotFoundError as e:
            raise RuntimeError(
                "The `claude` CLI was not found on PATH. Install Claude Code "
                "and log in, or use --llm-provider claude-api with ANTHROPIC_API_KEY."
            ) from e
        if proc.returncode != 0:
            raise RuntimeError(f"claude CLI exited {proc.returncode}: {proc.stderr.strip()}")

        payload = json.loads(proc.stdout)
        if payload.get("is_error"):
            raise RuntimeError(f"claude CLI returned an error: {payload.get('result')}")

        usage = payload.get("usage", {})
        input_tokens = (
            usage.get("input_tokens", 0)
            + usage.get("cache_creation_input_tokens", 0)
            + usage.get("cache_read_input_tokens", 0)
        )
        return LLMResponse(
            text=payload["result"],
            input_tokens=input_tokens,
            output_tokens=usage.get("output_tokens", 0),
            model=self._model,
            cost_usd=payload.get("total_cost_usd"),
        )
