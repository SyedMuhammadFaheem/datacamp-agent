"""dcai stats — pure SQLite read of token_usage/attempts aggregates."""

from dcai.config import Config
from dcai.db.connection import connect


def run(config: Config) -> int:
    conn = connect(config.db_path)
    try:
        totals = conn.execute(
            """
            SELECT provider, model, purpose,
                   SUM(input_tokens) AS in_tok, SUM(output_tokens) AS out_tok,
                   COUNT(*) AS calls, SUM(cost_usd) AS cost
            FROM token_usage GROUP BY provider, model, purpose
            """
        ).fetchall()
        if not totals:
            print("No usage recorded yet.")
        for row in totals:
            print(
                f"{row['provider']} {row['model'] or '-'} [{row['purpose']}]: "
                f"{row['calls']} calls, {row['in_tok']} in / {row['out_tok']} out tokens"
                + (f", ${row['cost']:.4f}" if row["cost"] else "")
            )

        cache_stats = conn.execute(
            """
            SELECT
                SUM(CASE WHEN input_tokens = 0 AND output_tokens = 0 THEN 1 ELSE 0 END) AS zero_token,
                COUNT(*) AS total
            FROM token_usage
            """
        ).fetchone()
        if cache_stats["total"]:
            rate = cache_stats["zero_token"] / cache_stats["total"] * 100
            print(f"Cache-hit rate: {rate:.1f}% ({cache_stats['zero_token']}/{cache_stats['total']} solve events)")

        attempt_stats = conn.execute(
            """
            SELECT result, COUNT(*) AS n FROM attempts GROUP BY result
            """
        ).fetchall()
        for row in attempt_stats:
            print(f"Attempts — {row['result']}: {row['n']}")
        return 0
    finally:
        conn.close()
