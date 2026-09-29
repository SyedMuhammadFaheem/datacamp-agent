"""dcai start <url> — first vertical slice: solves the single exercise
currently open at the given URL. Multi-exercise/chapter looping is out of
scope for this command until Phase 2 (see PROJECT_STATE.md)."""

import logging
import re
import urllib.error

from dcai.adapters.cdp import CDPAdapter
from dcai.adapters.cdp_transport import CDPError
from dcai.config import Config
from dcai.db import repo
from dcai.db.connection import connect
from dcai.llm import get_provider
from dcai.models import BlockedError
from dcai.normalize.exercise import instructions_hash, normalize
from dcai.solver.pipeline import solve

log = logging.getLogger(__name__)


def _slug_from_url(url: str) -> str:
    match = re.search(r"/courses/([a-z0-9-]+)", url)
    if match:
        return match.group(1)
    return url.rstrip("/").rsplit("/", 1)[-1]


def run(config: Config, url: str) -> int:
    slug = _slug_from_url(url)
    conn = connect(config.db_path)
    course_id = repo.upsert_course(conn, slug=slug, title=slug, url=url)
    chapter_id = repo.upsert_chapter(conn, course_id=course_id, chapter_number=1, title="Chapter 1")

    adapter = CDPAdapter(config.cdp_port)
    try:
        adapter.attach(url_hint=url)
        if url:
            adapter.navigate(url)

        exercise = normalize(adapter, exercise_id=url)
        # ponytail: exercise_number hardcoded to 1 until multi-exercise
        # looping (Phase 2) needs real chapter/exercise position tracking.
        exercise_db_id = repo.upsert_exercise(
            conn,
            chapter_id=chapter_id,
            exercise_number=1,
            type_=exercise.type.value,
            language=exercise.language,
            instructions=exercise.instructions,
            instructions_hash=instructions_hash(exercise.instructions, exercise.type.value, exercise.language),
            starter_code=exercise.starter_code,
            url=url,
        )

        provider = get_provider(config.llm_provider)
        result = solve(conn, adapter, provider, course_id, exercise_db_id, exercise)

        repo.set_state(conn, course_id, chapter_id, exercise_db_id, url)

        if result.success:
            log.info("Exercise solved and accepted by DataCamp.")
            return 0
        log.error("Exercise not accepted: %s", result.error_message)
        return 1
    except BlockedError as e:
        log.error("Blocked: %s", e)
        repo.set_course_status(conn, course_id, "blocked")
        return 2
    except (urllib.error.URLError, ConnectionRefusedError, CDPError) as e:
        log.error(
            "Could not reach Chrome DevTools Protocol on port %d (%s). "
            "Launch Chrome with --remote-debugging-port=%d, log into DataCamp, "
            "and try again.",
            config.cdp_port, e, config.cdp_port,
        )
        return 3
    finally:
        adapter.close()
        conn.close()
