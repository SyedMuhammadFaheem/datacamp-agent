import json
import sqlite3
from importlib import resources

import pytest

from dcai.migration.import_legacy import import_course


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
def legacy_course_dir(tmp_path):
    course_dir = tmp_path / "some-course"
    course_dir.mkdir()
    (course_dir / "state.json").write_text(
        json.dumps(
            {
                "course_url": "https://app.datacamp.com/learn/courses/some-course",
                "course_slug": "some-course",
                "course_title": "Some Course",
                "chapters": [
                    {"index": 1, "title": "Ch1", "url": "https://x/1", "status": "complete"},
                    {"index": 2, "title": "Ch2", "url": "https://x/2", "status": "not_started"},
                ],
                "current_chapter": 2,
                "current_lesson_ex": 1,
                "completed_lessons": [],
                "completed_exercises": [
                    {"chapter": 1, "ex": 1, "title": "First exercise", "xp": 100},
                    {"chapter": 1, "ex": 2, "title": "Second exercise", "xp": 50, "note": "hint used"},
                ],
                "failed_exercises": [],
                "blocked_items": [],
                "last_known_location": "Chapter 1 complete, starting chapter 2.",
                "last_updated": "2026-01-01",
            }
        )
    )
    (course_dir / "concepts.md").write_text(
        "# Notes\n\n## Chapter 1: Ch1\n\n### 1. A concept\nCONCEPT: Something.\nDEFINITION: Explained.\n"
    )
    (course_dir / "exercises.md").write_text(
        "# Log\n\n## Chapter 1: Ch1\n\n### Ex 1 — First exercise (100 XP)\n"
        "Result: Passed.\nKey lesson: use a list comprehension.\n"
    )
    return course_dir


def test_import_creates_course_chapters_and_exercises(conn, legacy_course_dir):
    course_id = import_course(conn, legacy_course_dir)

    course = conn.execute("SELECT * FROM courses WHERE id=?", (course_id,)).fetchone()
    assert course["slug"] == "some-course"
    assert course["status"] == "in_progress"

    chapters = conn.execute("SELECT * FROM chapters WHERE course_id=? ORDER BY chapter_number", (course_id,)).fetchall()
    assert [c["status"] for c in chapters] == ["completed", "not_started"]

    exercises = conn.execute(
        "SELECT * FROM exercises WHERE chapter_id=?", (chapters[0]["id"],)
    ).fetchall()
    assert len(exercises) == 2
    assert all(e["status"] == "solved" for e in exercises)


def test_import_is_idempotent(conn, legacy_course_dir):
    import_course(conn, legacy_course_dir)
    import_course(conn, legacy_course_dir)

    courses = conn.execute("SELECT * FROM courses").fetchall()
    assert len(courses) == 1
    memory = conn.execute("SELECT * FROM course_memory").fetchall()
    # Re-running must not duplicate memory rows: 1 concept block + 1
    # exercise "Key lesson" block + 1 gotcha from completed_exercises' note.
    assert len(memory) == 3


def test_import_preserves_exercise_notes_as_gotcha_memory(conn, legacy_course_dir):
    course_id = import_course(conn, legacy_course_dir)
    gotchas = conn.execute(
        "SELECT * FROM course_memory WHERE course_id=? AND kind='gotcha'", (course_id,)
    ).fetchall()
    assert any("hint used" in g["content"] for g in gotchas)
