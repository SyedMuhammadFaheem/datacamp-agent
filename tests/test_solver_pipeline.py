import sqlite3
from importlib import resources

import pytest

from dcai.db import repo
from dcai.models import Exercise, ExerciseType
from dcai.normalize.exercise import instructions_hash
from dcai.solver.pipeline import solve
from tests.fakes import FakeBrowserAdapter, FakeLLMProvider


@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    schema = resources.files("dcai.db").joinpath("schema.sql").read_text()
    connection.executescript(schema)
    yield connection
    connection.close()


@pytest.fixture
def course_and_chapter(conn):
    course_id = repo.upsert_course(conn, slug="c", title="C", url="https://x")
    chapter_id = repo.upsert_chapter(conn, course_id=course_id, chapter_number=1, title="Ch1")
    return course_id, chapter_id


def _make_exercise(instructions="Write a function that returns 1"):
    return Exercise(
        id="ex1",
        type=ExerciseType.CODING,
        language="python",
        instructions=instructions,
        starter_code="def f():\n    pass",
    )


def test_fresh_exercise_makes_exactly_one_llm_call(conn, course_and_chapter):
    course_id, chapter_id = course_and_chapter
    exercise = _make_exercise()
    exercise_db_id = repo.upsert_exercise(
        conn, chapter_id=chapter_id, exercise_number=1, type_="coding", language="python",
        instructions=exercise.instructions,
        instructions_hash=instructions_hash(exercise.instructions, "coding", "python"),
    )
    adapter = FakeBrowserAdapter(feedback=("success", None))
    provider = FakeLLMProvider(responses=["def f():\n    return 1"])

    result = solve(conn, adapter, provider, course_id, exercise_db_id, exercise)

    assert result.success
    assert provider.calls == 1


def test_cache_hit_makes_zero_llm_calls(conn, course_and_chapter):
    course_id, chapter_id = course_and_chapter
    exercise = _make_exercise()
    ihash = instructions_hash(exercise.instructions, "coding", "python")

    # Prime the cache: a prior exercise with the same instructions_hash has
    # a solution DataCamp actually accepted (a successful attempt against
    # it) — an unverified solution must not be cacheable (see
    # test_cache_requires_successful_attempt).
    prior_exercise_id = repo.upsert_exercise(
        conn, chapter_id=chapter_id, exercise_number=1, type_="coding", language="python",
        instructions=exercise.instructions, instructions_hash=ihash,
    )
    prior_solution_id = repo.insert_solution(conn, prior_exercise_id, ihash, "def f():\n    return 1", source="llm")
    repo.insert_attempt(conn, prior_exercise_id, prior_solution_id, "def f():\n    return 1", "success")

    new_exercise_id = repo.upsert_exercise(
        conn, chapter_id=chapter_id, exercise_number=2, type_="coding", language="python",
        instructions=exercise.instructions, instructions_hash=ihash,
    )
    adapter = FakeBrowserAdapter(feedback=("success", None))
    provider = FakeLLMProvider(responses=[])

    result = solve(conn, adapter, provider, course_id, new_exercise_id, exercise)

    assert result.success
    assert provider.calls == 0
    zero_token_rows = conn.execute(
        "SELECT COUNT(*) AS n FROM token_usage WHERE exercise_id=? AND input_tokens=0", (new_exercise_id,)
    ).fetchone()["n"]
    assert zero_token_rows == 1


def test_cache_requires_successful_attempt(conn, course_and_chapter):
    course_id, chapter_id = course_and_chapter
    exercise = _make_exercise()
    ihash = instructions_hash(exercise.instructions, "coding", "python")

    # A prior exercise has a current solution, but its only attempt failed —
    # this content must NOT be served from cache (see
    # repo.find_current_solution_by_hash).
    prior_exercise_id = repo.upsert_exercise(
        conn, chapter_id=chapter_id, exercise_number=1, type_="coding", language="python",
        instructions=exercise.instructions, instructions_hash=ihash,
    )
    prior_solution_id = repo.insert_solution(conn, prior_exercise_id, ihash, "def f():\n    return 999", source="llm")
    repo.insert_attempt(conn, prior_exercise_id, prior_solution_id, "def f():\n    return 999", "wrong_answer")

    new_exercise_id = repo.upsert_exercise(
        conn, chapter_id=chapter_id, exercise_number=2, type_="coding", language="python",
        instructions=exercise.instructions, instructions_hash=ihash,
    )
    adapter = FakeBrowserAdapter(feedback=("success", None))
    provider = FakeLLMProvider(responses=["def f():\n    return 1"])

    result = solve(conn, adapter, provider, course_id, new_exercise_id, exercise)

    assert result.success
    assert provider.calls == 1  # cache miss — the unverified content was not reused


def test_cache_does_not_leak_across_exercises_sharing_a_db_row(conn, course_and_chapter):
    """Regression for a live-verified bug: exercise_number is hardcoded to 1
    in start.py (Phase 1), so every exercise in a run shares one DB row
    whose instructions_hash column gets overwritten each time. A cache
    lookup that joined through that mutable column matched ANY solution
    ever attached to the row — e.g. an MCQ answer got submitted as the
    "cached" solution for a later, unrelated coding exercise. The fix keys
    solutions by their own immutable instructions_hash column instead."""
    course_id, chapter_id = course_and_chapter
    shared_exercise_id = repo.upsert_exercise(
        conn, chapter_id=chapter_id, exercise_number=1, type_="mcq", language="python",
        instructions="Old MCQ instructions",
        instructions_hash=instructions_hash("Old MCQ instructions", "mcq", "python"),
    )
    mcq_solution_id = repo.insert_solution(
        conn, shared_exercise_id, instructions_hash("Old MCQ instructions", "mcq", "python"), "2015", source="llm",
    )
    repo.insert_attempt(conn, shared_exercise_id, mcq_solution_id, "2015", "success")

    # Same DB row (exercise_number still 1), now reused for a different,
    # unrelated coding exercise — this is exactly what start.py does today.
    coding_exercise = _make_exercise(instructions="Create an OpenAI API client")
    repo.upsert_exercise(
        conn, chapter_id=chapter_id, exercise_number=1, type_="coding", language="python",
        instructions=coding_exercise.instructions,
        instructions_hash=instructions_hash(coding_exercise.instructions, "coding", "python"),
    )
    adapter = FakeBrowserAdapter(feedback=("success", None))
    provider = FakeLLMProvider(responses=["client = OpenAI()"])

    solve(conn, adapter, provider, course_id, shared_exercise_id, coding_exercise)

    assert provider.calls == 1  # must NOT reuse the MCQ's cached "2015"
    assert "2015" not in adapter.submitted


def test_mcq_solve_selects_and_submits_matching_option(conn, course_and_chapter):
    course_id, chapter_id = course_and_chapter
    exercise = Exercise(
        id="ex-mcq", type=ExerciseType.MCQ, language="python",
        instructions="In what year was OpenAI founded?",
        context={"options": ["2022", "2020", "2017", "2015"]},
    )
    exercise_db_id = repo.upsert_exercise(
        conn, chapter_id=chapter_id, exercise_number=1, type_="mcq", language="python",
        instructions=exercise.instructions,
        instructions_hash=instructions_hash(exercise.instructions, "mcq", "python"),
    )
    adapter = FakeBrowserAdapter(feedback=("success", None))
    provider = FakeLLMProvider(responses=["2015"])

    result = solve(conn, adapter, provider, course_id, exercise_db_id, exercise)

    assert result.success
    assert provider.calls == 1
    assert adapter.selected_option == 3  # index of "2015"


def test_mcq_wrong_answer_does_not_trigger_code_repair(conn, course_and_chapter):
    course_id, chapter_id = course_and_chapter
    exercise = Exercise(
        id="ex-mcq", type=ExerciseType.MCQ, language="python",
        instructions="In what year was OpenAI founded?",
        context={"options": ["2022", "2020", "2017", "2015"]},
    )
    exercise_db_id = repo.upsert_exercise(
        conn, chapter_id=chapter_id, exercise_number=1, type_="mcq", language="python",
        instructions=exercise.instructions,
        instructions_hash=instructions_hash(exercise.instructions, "mcq", "python"),
    )
    adapter = FakeBrowserAdapter(feedback=("wrong_answer", None))
    provider = FakeLLMProvider(responses=["2022"])

    result = solve(conn, adapter, provider, course_id, exercise_db_id, exercise)

    assert not result.success
    assert provider.calls == 1  # no repair call — repair is code-only


def test_video_page_advances_without_llm_call(conn, course_and_chapter):
    course_id, chapter_id = course_and_chapter
    exercise = Exercise(id="ex-video", type=ExerciseType.VIDEO, language="python", instructions="")
    exercise_db_id = repo.upsert_exercise(
        conn, chapter_id=chapter_id, exercise_number=1, type_="video", language="python",
        instructions="", instructions_hash=instructions_hash("", "video", "python"),
    )
    adapter = FakeBrowserAdapter(got_it_present=True)
    provider = FakeLLMProvider(responses=[])

    result = solve(conn, adapter, provider, course_id, exercise_db_id, exercise)

    assert result.success
    assert provider.calls == 0
    assert adapter.clicked_button_texts == ["Got It!"]


def test_video_page_without_continue_control_fails_cleanly(conn, course_and_chapter):
    course_id, chapter_id = course_and_chapter
    exercise = Exercise(id="ex-theory", type=ExerciseType.THEORY, language="python", instructions="")
    exercise_db_id = repo.upsert_exercise(
        conn, chapter_id=chapter_id, exercise_number=1, type_="theory", language="python",
        instructions="", instructions_hash=instructions_hash("", "theory", "python"),
    )
    adapter = FakeBrowserAdapter(got_it_present=False)
    provider = FakeLLMProvider(responses=[])

    result = solve(conn, adapter, provider, course_id, exercise_db_id, exercise)

    assert not result.success
    assert provider.calls == 0


def test_repair_loop_sends_only_code_and_error(conn, course_and_chapter):
    course_id, chapter_id = course_and_chapter
    exercise = _make_exercise()
    exercise_db_id = repo.upsert_exercise(
        conn, chapter_id=chapter_id, exercise_number=1, type_="coding", language="python",
        instructions=exercise.instructions,
        instructions_hash=instructions_hash(exercise.instructions, "coding", "python"),
    )
    adapter = FakeBrowserAdapter(feedback=("error", "NameError: x is not defined"))
    provider = FakeLLMProvider(responses=["def f():\n    return 1", "def f():\n    return 2"])

    result = solve(conn, adapter, provider, course_id, exercise_db_id, exercise)

    assert not result.success
    assert provider.calls == 2  # initial solve + one repair attempt (cap=1)
