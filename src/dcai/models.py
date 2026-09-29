from dataclasses import dataclass, field
from enum import Enum


class ExerciseType(str, Enum):
    CODING = "coding"
    SQL_CODING = "sql_coding"
    MCQ = "mcq"
    DRAG_DROP = "drag_drop"
    VIDEO = "video"
    THEORY = "theory"


@dataclass
class Exercise:
    """Normalized exercise state. Never holds raw HTML or a screenshot —
    only text extracted via JS getters. This is the only thing that may
    ever reach an LLM prompt."""

    id: str
    type: ExerciseType
    language: str
    instructions: str
    starter_code: str | None = None
    current_code: str | None = None
    context: dict = field(default_factory=dict)
    hints: list[str] = field(default_factory=list)
    error_output: str | None = None


@dataclass
class SolveResult:
    success: bool
    content: str
    source: str  # 'cache' | 'deterministic' | 'llm'
    input_tokens: int = 0
    output_tokens: int = 0
    model: str | None = None
    error_message: str | None = None


class BlockedError(Exception):
    """Raised when a CAPTCHA, MFA, paywall, or other access-control
    mechanism blocks automation. Must halt the pipeline immediately —
    never routed through the LLM, never bypassed."""
