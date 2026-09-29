import sqlite3
from importlib import resources

import pytest


@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    schema = resources.files("dcai.db").joinpath("schema.sql").read_text()
    connection.executescript(schema)
    yield connection
    connection.close()


def test_course_slug_is_unique(conn):
    now = "2026-01-01T00:00:00"
    conn.execute(
        "INSERT INTO courses (slug, title, url, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        ("foo", "Foo", "https://x", now, now),
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO courses (slug, title, url, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            ("foo", "Foo2", "https://y", now, now),
        )


def test_exercise_status_check_constraint(conn):
    now = "2026-01-01T00:00:00"
    conn.execute(
        "INSERT INTO courses (slug, title, url, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        ("foo", "Foo", "https://x", now, now),
    )
    course_id = conn.execute("SELECT id FROM courses").fetchone()["id"]
    conn.execute(
        "INSERT INTO chapters (course_id, chapter_number, title) VALUES (?, ?, ?)",
        (course_id, 1, "Ch1"),
    )
    chapter_id = conn.execute("SELECT id FROM chapters").fetchone()["id"]
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO exercises (chapter_id, exercise_number, type, instructions_hash, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (chapter_id, 1, "coding", "hash", "not_a_real_status"),
        )


def test_instructions_hash_lookup_index(conn):
    now = "2026-01-01T00:00:00"
    conn.execute(
        "INSERT INTO courses (slug, title, url, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        ("foo", "Foo", "https://x", now, now),
    )
    course_id = conn.execute("SELECT id FROM courses").fetchone()["id"]
    conn.execute("INSERT INTO chapters (course_id, chapter_number, title) VALUES (?, ?, ?)", (course_id, 1, "Ch1"))
    chapter_id = conn.execute("SELECT id FROM chapters").fetchone()["id"]
    conn.execute(
        """
        INSERT INTO exercises (chapter_id, exercise_number, type, instructions_hash, status)
        VALUES (?, ?, ?, ?, 'solved')
        """,
        (chapter_id, 1, "coding", "abc123"),
    )
    row = conn.execute("SELECT * FROM exercises WHERE instructions_hash=?", ("abc123",)).fetchone()
    assert row is not None
    assert row["status"] == "solved"
