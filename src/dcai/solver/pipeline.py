"""cache -> deterministic -> llm -> submit -> validate -> repair.

Every branch writes one attempts row and one token_usage row (zeros for
cache/deterministic hits), so dcai stats' cache-hit-rate is a plain
aggregate query.
"""

import sqlite3
import time

from dcai.adapters import selectors
from dcai.adapters.base import BrowserAdapter
from dcai.db import repo
from dcai.llm.base import LLMProvider
from dcai.models import Exercise, ExerciseType, SolveResult
from dcai.normalize.exercise import instructions_hash
from dcai.solver import deterministic, llm_solver
from dcai.solver import repair as repair_mod

MAX_REPAIR_ATTEMPTS = 1

# ponytail: goes straight to LLM repair on failure rather than retrying the
# identical submission first (transient UI/timing failures aren't a
# confirmed failure mode yet); add a same-content retry pass before repair
# if live runs show submissions failing transiently.


NON_EXERCISE_TYPES = (ExerciseType.VIDEO, ExerciseType.THEORY)


def solve(
    conn: sqlite3.Connection,
    adapter: BrowserAdapter,
    provider: LLMProvider,
    course_id: int,
    exercise_db_id: int,
    exercise: Exercise,
) -> SolveResult:
    if exercise.type in NON_EXERCISE_TYPES:
        return _advance_non_exercise(conn, adapter, exercise_db_id)

    ihash = instructions_hash(exercise.instructions, exercise.type.value, exercise.language)

    content, source = _get_solution(conn, exercise, ihash)
    input_tokens = output_tokens = 0
    model = cost_usd = None

    if content is None:
        is_mcq = exercise.type == ExerciseType.MCQ
        solved = llm_solver.solve_mcq(provider, exercise) if is_mcq else llm_solver.solve(provider, exercise)
        if solved is None:
            msg = "LLM produced invalid answer" if is_mcq else "LLM produced invalid code"
            result = SolveResult(success=False, content="", source="llm", error_message=msg)
            repo.insert_attempt(conn, exercise_db_id, None, None, "error", result.error_message)
            repo.insert_token_usage(conn, course_id, exercise_db_id, provider.name, None, 0, 0, "solve")
            return result
        content, response = solved
        source = "llm"
        input_tokens, output_tokens, model, cost_usd = (
            response.input_tokens, response.output_tokens, response.model, response.cost_usd,
        )

    solution_id = repo.insert_solution(conn, exercise_db_id, ihash, content, source)
    repo.insert_token_usage(
        conn, course_id, exercise_db_id, provider.name, model, input_tokens, output_tokens, "solve", cost_usd,
    )

    result = _submit_and_validate(conn, adapter, exercise_db_id, solution_id, content, exercise)

    # Code repair only: the repair loop asks the LLM to fix code given a
    # syntax/runtime error, which doesn't apply to an MCQ answer — a wrong
    # MCQ pick with no code to repair is just recorded as failed.
    attempts = 0
    is_coding = exercise.type in (ExerciseType.CODING, ExerciseType.SQL_CODING)
    while is_coding and not result.success and attempts < MAX_REPAIR_ATTEMPTS and result.error_message:
        attempts += 1
        fixed = repair_mod.repair(provider, content, result.error_message, exercise.language)
        if fixed is None:
            repo.insert_token_usage(conn, course_id, exercise_db_id, provider.name, None, 0, 0, "repair")
            break
        content, response = fixed
        solution_id = repo.insert_solution(conn, exercise_db_id, ihash, content, "llm")
        repo.insert_token_usage(
            conn, course_id, exercise_db_id, provider.name, response.model,
            response.input_tokens, response.output_tokens, "repair", response.cost_usd,
        )
        result = _submit_and_validate(conn, adapter, exercise_db_id, solution_id, content, exercise)

    repo.set_exercise_status(conn, exercise_db_id, "solved" if result.success else "failed")
    return result


def _advance_non_exercise(conn: sqlite3.Connection, adapter: BrowserAdapter, exercise_db_id: int) -> SolveResult:
    """Video/theory pages have nothing to solve — just click past them. No
    LLM call, no cache, no submission; recorded the same way as any other
    attempt so `dcai status`/`stats` sees it."""
    found = adapter.click_button_with_text(selectors.GOT_IT_BUTTON_TEXT)
    if not found:
        result = SolveResult(
            success=False, content="", source="none",
            error_message="No 'Got It!' control found on this video/theory page",
        )
        repo.insert_attempt(conn, exercise_db_id, None, None, "error", result.error_message)
        repo.set_exercise_status(conn, exercise_db_id, "failed")
        return result

    result = SolveResult(success=True, content="", source="none")
    repo.insert_attempt(conn, exercise_db_id, None, None, "success")
    repo.set_exercise_status(conn, exercise_db_id, "solved")
    return result


def _get_solution(conn: sqlite3.Connection, exercise: Exercise, ihash: str) -> tuple[str | None, str]:
    cached = repo.find_current_solution_by_hash(conn, ihash)
    if cached is not None:
        return cached["content"], "cache"
    det = deterministic.try_solve(exercise)
    if det is not None:
        return det, "deterministic"
    return None, "llm"


def _submit_and_validate(
    conn: sqlite3.Connection,
    adapter: BrowserAdapter,
    exercise_db_id: int,
    solution_id: int,
    content: str,
    exercise: Exercise,
) -> SolveResult:
    start = time.monotonic()
    if exercise.type == ExerciseType.MCQ:
        adapter.select_option(exercise.context["options"].index(content))
    else:
        adapter.set_editor_content(content)
    adapter.submit()
    outcome, error_text = adapter.get_feedback()
    duration_ms = int((time.monotonic() - start) * 1000)

    attempt_result = {"success": "success", "error": "error", "wrong_answer": "wrong_answer", "pending": "timeout"}[outcome]
    repo.insert_attempt(conn, exercise_db_id, solution_id, content, attempt_result, error_text, duration_ms)

    return SolveResult(
        success=(outcome == "success"),
        content=content,
        source="submitted",
        error_message=error_text or ("Submission did not complete in time" if outcome == "pending" else None),
    )
