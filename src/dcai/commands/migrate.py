"""dcai migrate — one-time import of the legacy markdown/JSON workflow
into SQLite. Idempotent: safe to re-run."""

import logging
from pathlib import Path

from dcai.config import Config
from dcai.db.connection import connect
from dcai.migration.import_legacy import import_course

log = logging.getLogger(__name__)


def run(config: Config, legacy_dir: str) -> int:
    base = Path(legacy_dir)
    if not base.is_dir():
        log.error("Legacy directory not found: %s", base)
        return 1

    conn = connect(config.db_path)
    try:
        imported = 0
        for course_dir in sorted(base.iterdir()):
            if not (course_dir / "state.json").exists():
                continue
            import_course(conn, course_dir)
            log.info("Imported %s", course_dir.name)
            imported += 1
        if imported == 0:
            log.warning("No legacy courses found under %s", base)
            return 1
        return 0
    finally:
        conn.close()
