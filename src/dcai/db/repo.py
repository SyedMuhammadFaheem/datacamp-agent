"""Plain parameterized-SQL functions per table. No ORM — the schema is
small and simple enough that hand-written SQL is less code and less magic."""

import hashlib
import sqlite3
from datetime import UTC, datetime


def _now() -> str:
    return datetime.now(UTC).isoformat()


# --- courses -----------------------------------------------------------

def upsert_course(conn: sqlite3.Connection, slug: str, title: str, url: str, type_: str = "course") -> int:
    now = _now()
    conn.execute(
        """
        INSERT INTO courses (slug, title, url, type, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(slug) DO UPDATE SET title=excluded.title, url=excluded.url, updated_at=excluded.updated_at
        """,
        (slug, title, url, type_, now, now),
    )
    conn.commit()
    return conn.execute("SELECT id FROM courses WHERE slug=?", (slug,)).fetchone()["id"]


def set_course_status(conn: sqlite3.Connection, course_id: int, status: str) -> None:
    conn.execute(
        "UPDATE courses SET status=?, updated_at=? WHERE id=?", (status, _now(), course_id)
    )
    conn.commit()


def get_course_by_slug(conn: sqlite3.Connection, slug: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM courses WHERE slug=?", (slug,)).fetchone()


# --- chapters ------------------------------------------------------------

def upsert_chapter(
    conn: sqlite3.Connection, course_id: int, chapter_number: int, title: str, slug: str | None = None
) -> int:
    conn.execute(
        """
        INSERT INTO chapters (course_id, chapter_number, slug, title)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(course_id, chapter_number) DO UPDATE SET title=excluded.title, slug=excluded.slug
        """,
        (course_id, chapter_number, slug, title),
    )
    conn.commit()
    return conn.execute(
        "SELECT id FROM chapters WHERE course_id=? AND chapter_number=?", (course_id, chapter_number)
    ).fetchone()["id"]


def set_chapter_status(conn: sqlite3.Connection, chapter_id: int, status: str) -> None:
    conn.execute("UPDATE chapters SET status=? WHERE id=?", (status, chapter_id))
    conn.commit()


# --- exercises -----------------------------------------------------------

def upsert_exercise(
    conn: sqlite3.Connection,
    chapter_id: int,
    exercise_number: int,
    type_: str,
    language: str,
    instructions: str,
    instructions_hash: str,
    starter_code: str | None = None,
    url: str | None = None,
    dc_exercise_id: str | None = None,
) -> int:
    conn.execute(
        """
        INSERT INTO exercises
            (chapter_id, exercise_number, dc_exercise_id, url, type, language,
             instructions, instructions_hash, starter_code)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(chapter_id, exercise_number) DO UPDATE SET
            type=excluded.type, language=excluded.language,
            instructions=excluded.instructions, instructions_hash=excluded.instructions_hash,
            starter_code=excluded.starter_code
        """,
        (chapter_id, exercise_number, dc_exercise_id, url, type_, language, instructions, instructions_hash, starter_code),
    )
    conn.commit()
    return conn.execute(
        "SELECT id FROM exercises WHERE chapter_id=? AND exercise_number=?", (chapter_id, exercise_number)
    ).fetchone()["id"]


def set_exercise_status(conn: sqlite3.Connection, exercise_id: int, status: str) -> None:
    solved_at = _now() if status == "solved" else None
    conn.execute(
        "UPDATE exercises SET status=?, solved_at=? WHERE id=?", (status, solved_at, exercise_id)
    )
    conn.commit()


def find_exercise_by_hash(conn: sqlite3.Connection, instructions_hash: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM exercises WHERE instructions_hash=? AND status='solved' LIMIT 1", (instructions_hash,)
    ).fetchone()


# --- solutions -------------------------------------------------------------

def find_current_solution_by_hash(conn: sqlite3.Connection, instructions_hash: str) -> sqlite3.Row | None:
    # Matches on solutions.instructions_hash (captured at insert time, never
    # mutated) rather than joining through exercises.instructions_hash — the
    # exercises row is shared/overwritten across runs while
    # exercise_number stays hardcoded to 1 (see start.py), so a join on its
    # *current* hash column would vacuously match any solution ever
    # attached to that row, regardless of which exercise it was really for.
    #
    # Success-gated: a solution is only cacheable once it has at least one
    # attempt DataCamp actually accepted. Without this, a wrong/erroring
    # attempt's content becomes "the answer" for every future exercise with
    # the same instructions_hash (any course, forever) and the solver keeps
    # resubmitting known-bad content via the cache path instead of ever
    # asking the LLM to reconsider.
    return conn.execute(
        """
        SELECT s.* FROM solutions s
        WHERE s.instructions_hash = ?
          AND EXISTS (
              SELECT 1 FROM attempts a WHERE a.solution_id = s.id AND a.result = 'success'
          )
        ORDER BY s.created_at DESC LIMIT 1
        """,
        (instructions_hash,),
    ).fetchone()


def insert_solution(
    conn: sqlite3.Connection, exercise_id: int, instructions_hash: str, content: str, source: str
) -> int:
    content_hash = hashlib.sha256(content.encode()).hexdigest()
    conn.execute("UPDATE solutions SET is_current=0 WHERE exercise_id=?", (exercise_id,))
    cur = conn.execute(
        """
        INSERT INTO solutions (exercise_id, instructions_hash, content, content_hash, source, is_current, created_at)
        VALUES (?, ?, ?, ?, ?, 1, ?)
        """,
        (exercise_id, instructions_hash, content, content_hash, source, _now()),
    )
    conn.commit()
    return cur.lastrowid


# --- attempts ----------------------------------------------------------------

def insert_attempt(
    conn: sqlite3.Connection,
    exercise_id: int,
    solution_id: int | None,
    submitted_content: str | None,
    result: str,
    error_message: str | None = None,
    duration_ms: int | None = None,
) -> int:
    attempt_number = (
        conn.execute(
            "SELECT COALESCE(MAX(attempt_number), 0) + 1 AS n FROM attempts WHERE exercise_id=?",
            (exercise_id,),
        ).fetchone()["n"]
    )
    cur = conn.execute(
        """
        INSERT INTO attempts
            (exercise_id, attempt_number, solution_id, submitted_content, result, error_message, duration_ms, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (exercise_id, attempt_number, solution_id, submitted_content, result, error_message, duration_ms, _now()),
    )
    conn.commit()
    return cur.lastrowid


# --- token usage ---------------------------------------------------------------

def insert_token_usage(
    conn: sqlite3.Connection,
    course_id: int | None,
    exercise_id: int | None,
    provider: str,
    model: str | None,
    input_tokens: int,
    output_tokens: int,
    purpose: str,
    cost_usd: float | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO token_usage
            (exercise_id, course_id, provider, model, input_tokens, output_tokens, cost_usd, purpose, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (exercise_id, course_id, provider, model, input_tokens, output_tokens, cost_usd, purpose, _now()),
    )
    conn.commit()


# --- state (resume checkpoint) --------------------------------------------------

def set_state(
    conn: sqlite3.Connection,
    course_id: int,
    current_chapter_id: int | None,
    current_exercise_id: int | None,
    last_url: str | None,
    notes: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO state (course_id, current_chapter_id, current_exercise_id, last_url, notes, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(course_id) DO UPDATE SET
            current_chapter_id=excluded.current_chapter_id,
            current_exercise_id=excluded.current_exercise_id,
            last_url=excluded.last_url, notes=excluded.notes, updated_at=excluded.updated_at
        """,
        (course_id, current_chapter_id, current_exercise_id, last_url, notes, _now()),
    )
    conn.commit()


def get_state(conn: sqlite3.Connection, course_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM state WHERE course_id=?", (course_id,)).fetchone()


def latest_state(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM state ORDER BY updated_at DESC LIMIT 1").fetchone()


# --- course memory (notes) ------------------------------------------------------

def add_memory(
    conn: sqlite3.Connection, course_id: int, chapter_id: int | None, kind: str, content: str
) -> None:
    conn.execute(
        """
        INSERT INTO course_memory (course_id, chapter_id, kind, content, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (course_id, chapter_id, kind, content, _now()),
    )
    conn.commit()


def list_memory(conn: sqlite3.Connection, course_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM course_memory WHERE course_id=? ORDER BY id", (course_id,)
    ).fetchall()
