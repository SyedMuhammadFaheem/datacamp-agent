import argparse
import logging
import sys

from dcai.config import load_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dcai")
    parser.add_argument("--cdp-port", type=int, default=None)
    parser.add_argument("--db-path", type=str, default=None)
    parser.add_argument("--llm-provider", type=str, default=None)
    parser.add_argument("-v", "--verbose", action="store_true")

    sub = parser.add_subparsers(dest="command", required=True)

    p_start = sub.add_parser("start", help="Start (or continue) a course by URL")
    p_start.add_argument("url")

    p_resume = sub.add_parser("resume", help="Resume the most recent (or named) course")
    p_resume.add_argument("--course", type=str, default=None)
    p_resume.add_argument("--limit", type=int, default=5)

    p_status = sub.add_parser("status", help="Show progress for a course")
    p_status.add_argument("--course", type=str, default=None)

    sub.add_parser("stats", help="Show token usage and solve statistics")

    p_notes = sub.add_parser("notes", help="Render accumulated course notes")
    p_notes.add_argument("course", nargs="?", default=None)
    p_notes.add_argument("--out", type=str, default=None)
    p_notes.add_argument("--regenerate", action="store_true")

    p_migrate = sub.add_parser("migrate", help="Import legacy markdown/JSON progress into SQLite")
    p_migrate.add_argument("--legacy-dir", type=str, default="courses")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(message)s")

    config = load_config(
        db_path=args.db_path, cdp_port=args.cdp_port, llm_provider=args.llm_provider, verbose=args.verbose
    )

    from dcai.commands import migrate, notes, resume, start, stats, status

    handlers = {
        "start": lambda: start.run(config, args.url),
        "resume": lambda: resume.run(config, args.course, args.limit),
        "status": lambda: status.run(config, args.course),
        "stats": lambda: stats.run(config),
        "notes": lambda: notes.run(config, args.course, args.out, args.regenerate),
        "migrate": lambda: migrate.run(config, args.legacy_dir),
    }
    return handlers[args.command]() or 0


if __name__ == "__main__":
    sys.exit(main())
