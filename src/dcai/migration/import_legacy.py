"""One-time, idempotent import of the old markdown/JSON progress-tracking
workflow (courses/<slug>/{state.json,concepts.md,exercises.md}) into the
SQLite schema. Field mapping is taken directly from the real legacy files
of the original workflow (a course directory such as
courses/deep-learning-for-images-with-pytorch/), not guessed.

state.json shape (confirmed): course_url, course_slug, course_title,
chapters: [{index, title, url, status}], completed_exercises:
[{chapter, ex, title, xp, note?}], completed_lessons (videos, same shape
minus xp), failed_exercises, blocked_items.

concepts.md / exercises.md shape (confirmed): "## Chapter N: Title"
sections containing "### ..." blocks of free-form notes.
"""

import json
import re
import sqlite3
from pathlib import Path

from dcai.db import repo
from dcai.normalize.exercise import instructions_hash

CHAPTER_SECTION_RE = re.compile(r"^## Chapter (\d+):\s*(.*)$", re.MULTILINE)
SUBSECTION_RE = re.compile(r"^### .+$", re.MULTILINE)


def _split_chapter_sections(markdown: str) -> dict[int, str]:
    """Splits a concepts.md/exercises.md-style file into {chapter_number: body}."""
    sections: dict[int, str] = {}
    matches = list(CHAPTER_SECTION_RE.finditer(markdown))
    for i, match in enumerate(matches):
        chapter_num = int(match.group(1))
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(markdown)
        sections[chapter_num] = markdown[start:end]
    return sections


def _split_subsections(body: str) -> list[str]:
    headers = list(SUBSECTION_RE.finditer(body))
    blocks = []
    for i, match in enumerate(headers):
        start = match.start()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(body)
        blocks.append(body[start:end].strip())
    return blocks


def import_course(conn: sqlite3.Connection, course_dir: Path) -> int:
    state_path = course_dir / "state.json"
    state = json.loads(state_path.read_text())

    course_id = repo.upsert_course(
        conn,
        slug=state["course_slug"],
        title=state["course_title"],
        url=state["course_url"],
    )
    if state.get("blocked_items"):
        repo.set_course_status(conn, course_id, "blocked")
    elif all(c["status"] == "complete" for c in state["chapters"]):
        repo.set_course_status(conn, course_id, "completed")
    else:
        repo.set_course_status(conn, course_id, "in_progress")

    # course_memory has no natural upsert key (free-form blocks), so make
    # re-running idempotent by clearing this course's memory before
    # re-importing rather than accumulating duplicates.
    conn.execute("DELETE FROM course_memory WHERE course_id=?", (course_id,))
    conn.commit()

    chapter_ids: dict[int, int] = {}
    for chapter in state["chapters"]:
        status = {"complete": "completed", "not_started": "not_started"}.get(
            chapter["status"], "in_progress"
        )
        chapter_id = repo.upsert_chapter(
            conn, course_id=course_id, chapter_number=chapter["index"], title=chapter["title"]
        )
        repo.set_chapter_status(conn, chapter_id, status)
        chapter_ids[chapter["index"]] = chapter_id

    for entry in state.get("completed_exercises", []):
        chapter_id = chapter_ids.get(entry["chapter"])
        if chapter_id is None:
            continue
        title = entry["title"]
        exercise_id = repo.upsert_exercise(
            conn,
            chapter_id=chapter_id,
            exercise_number=entry["ex"],
            type_="coding",
            language=state.get("language", "python"),
            instructions=title,
            instructions_hash=instructions_hash(title, "coding", "python"),
        )
        repo.set_exercise_status(conn, exercise_id, "solved")
        if entry.get("note"):
            repo.add_memory(conn, course_id, chapter_id, "gotcha", f"Ex {entry['ex']} ({title}): {entry['note']}")

    if state.get("last_known_location"):
        repo.set_state(
            conn,
            course_id=course_id,
            current_chapter_id=chapter_ids.get(state.get("current_chapter")),
            current_exercise_id=None,
            last_url=None,
            notes=state["last_known_location"],
        )

    concepts_path = course_dir / "concepts.md"
    if concepts_path.exists():
        for chapter_num, body in _split_chapter_sections(concepts_path.read_text()).items():
            chapter_id = chapter_ids.get(chapter_num)
            if chapter_id is None:
                continue
            for block in _split_subsections(body):
                repo.add_memory(conn, course_id, chapter_id, "concept", block)

    exercises_path = course_dir / "exercises.md"
    if exercises_path.exists():
        for chapter_num, body in _split_chapter_sections(exercises_path.read_text()).items():
            chapter_id = chapter_ids.get(chapter_num)
            if chapter_id is None:
                continue
            for block in _split_subsections(body):
                if "Key lesson" in block or "Note:" in block:
                    repo.add_memory(conn, course_id, chapter_id, "pattern", block)

    return course_id
