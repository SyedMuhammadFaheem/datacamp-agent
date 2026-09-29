"""dcai resume — reattaches and continues from the last checkpoint.

Phase 1 scope: re-solves the single exercise at the last checkpointed URL
(mirrors `start`). Walking forward through subsequent chapters/exercises
automatically is Phase 2 — it needs a confirmed way to detect and navigate
to "next exercise" in the live DOM, which hasn't been inspected yet.
"""

import logging

from dcai.commands import start
from dcai.config import Config
from dcai.db import repo
from dcai.db.connection import connect

log = logging.getLogger(__name__)


def run(config: Config, course_slug: str | None, limit: int) -> int:
    conn = connect(config.db_path)
    try:
        if course_slug:
            course = repo.get_course_by_slug(conn, course_slug)
            if course is None:
                log.error("No course found with slug %r", course_slug)
                return 1
            state = repo.get_state(conn, course["id"])
        else:
            state = repo.latest_state(conn)

        if state is None or not state["last_url"]:
            log.error("No checkpoint to resume from. Run `dcai start <url>` first.")
            return 1
    finally:
        conn.close()

    return start.run(config, state["last_url"])
