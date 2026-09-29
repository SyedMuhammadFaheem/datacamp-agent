"""dcai notes — renders accumulated course_memory as markdown. Read+render
only by default (token-free); --regenerate is the only path that spends
LLM tokens, and only for unusually dense chapters (Phase 2)."""

import logging
import sys

from dcai.config import Config
from dcai.db import repo
from dcai.db.connection import connect

log = logging.getLogger(__name__)


def run(config: Config, course_slug: str | None, out_path: str | None, regenerate: bool) -> int:
    if regenerate:
        log.warning("--regenerate is not implemented yet (Phase 2); rendering existing notes only.")

    conn = connect(config.db_path)
    try:
        if course_slug:
            course = repo.get_course_by_slug(conn, course_slug)
            if course is None:
                log.error("No course found with slug %r", course_slug)
                return 1
            courses = [course]
        else:
            courses = conn.execute("SELECT * FROM courses").fetchall()

        lines = []
        for course in courses:
            lines.append(f"# {course['title']}\n")
            for entry in repo.list_memory(conn, course["id"]):
                lines.append(f"- **[{entry['kind']}]** {entry['content']}")
            lines.append("")

        text = "\n".join(lines) if lines else "No notes recorded yet."
        if out_path:
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(text)
        else:
            sys.stdout.write(text + "\n")
        return 0
    finally:
        conn.close()
