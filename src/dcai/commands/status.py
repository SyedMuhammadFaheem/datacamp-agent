"""dcai status — pure SQLite read. No browser reads, no LLM calls."""

from dcai.config import Config
from dcai.db.connection import connect


def run(config: Config, course_slug: str | None) -> int:
    conn = connect(config.db_path)
    try:
        courses = conn.execute(
            "SELECT * FROM courses" + (" WHERE slug=?" if course_slug else ""),
            (course_slug,) if course_slug else (),
        ).fetchall()
        if not courses:
            print("No courses tracked yet. Run `dcai start <url>` first.")
            return 1
        for course in courses:
            print(f"{course['title']} ({course['slug']}) — {course['status']}")
            chapters = conn.execute(
                "SELECT * FROM chapters WHERE course_id=? ORDER BY chapter_number", (course["id"],)
            ).fetchall()
            for chapter in chapters:
                counts = conn.execute(
                    """
                    SELECT status, COUNT(*) AS n FROM exercises
                    WHERE chapter_id=? GROUP BY status
                    """,
                    (chapter["id"],),
                ).fetchall()
                summary = ", ".join(f"{row['status']}={row['n']}" for row in counts) or "no exercises tracked"
                print(f"  Chapter {chapter['chapter_number']} — {chapter['title']} [{chapter['status']}] ({summary})")
        return 0
    finally:
        conn.close()
