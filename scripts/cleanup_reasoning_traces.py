"""
Remove GLM reasoning traces that were stored as "enrichment" memories.

Before the stream-truncation fix, a thinking model that ran out of tokens had
its raw reasoning ("1. **Analyze the Request:** ...") returned as the answer,
and the auto-enrich / session_learn paths saved it to vectors.db.

Only rows that satisfy BOTH conditions are candidates:
  1. topic starts with 'glm:' or 'glm_session_insights:'  (written by GLM paths)
  2. content opens like a reasoning trace                  (see TRACE_PATTERNS)
Real GLM analyses ("# Auto-Enrich Analysis: ...") are kept.

Default is a dry run. With --apply the script first writes a consistent backup
(VACUUM INTO) and a JSONL tombstone of the deleted rows, then deletes them by
id in a single transaction.

Usage:
    py scripts/cleanup_reasoning_traces.py --db C:\\path\\to\\.codebase-memory\\vectors.db
    py scripts/cleanup_reasoning_traces.py --db ... --show-kept     # also list rows that are kept
    py scripts/cleanup_reasoning_traces.py --db ... --apply
"""

import argparse
import json
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

TOPIC_PREFIXES = ("glm:", "glm_session_insights:")

# Matched against the first 300 characters of the content.
TRACE_PATTERNS = [
    # Numbered/bold planning steps: "1. **Analyze the Request:**", "1. **Understand the Goal**"
    re.compile(r"^\s*(\d+\.\s*)?\*\*(Analy[sz]e|Understand|Deconstruct|Break\s*down|Identify)\b", re.I),
    # First-person / meta narration of the prompt
    re.compile(r"^\s*(The user\b|The request\b|I need to\b|I should\b|I'll\b|Let me\b|Okay\b|Thinking\b)", re.I),
]


def is_trace(content: str) -> bool:
    head = content[:300]
    return any(p.match(head) for p in TRACE_PATTERNS)


def one_line(text: str, width: int = 90) -> str:
    return re.sub(r"\s+", " ", text)[:width]


def connect(db: Path, readonly: bool) -> sqlite3.Connection:
    uri = f"file:{db.as_posix()}?mode={'ro' if readonly else 'rw'}"
    conn = sqlite3.connect(uri, uri=True, timeout=30)
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def find_candidates(conn: sqlite3.Connection):
    where = " OR ".join("topic LIKE ?" for _ in TOPIC_PREFIXES)
    rows = conn.execute(
        f"SELECT id, topic, category, content, metadata_json, created_at FROM vectors WHERE {where} ORDER BY created_at",
        [p + "%" for p in TOPIC_PREFIXES],
    ).fetchall()
    traces = [r for r in rows if is_trace(r[3])]
    kept = [r for r in rows if not is_trace(r[3])]
    return traces, kept


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", required=True, type=Path, help="path to vectors.db")
    ap.add_argument("--apply", action="store_true", help="delete (default is a dry run)")
    ap.add_argument("--show-kept", action="store_true", help="also list GLM rows that will be kept")
    args = ap.parse_args()

    if not args.db.is_file():
        print(f"not found: {args.db}", file=sys.stderr)
        return 2

    conn = connect(args.db, readonly=not args.apply)
    try:
        total = conn.execute("SELECT COUNT(*) FROM vectors").fetchone()[0]
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        traces, kept = find_candidates(conn)

        print(f"db: {args.db}  (journal_mode={mode}, {total} rows)")
        print(f"GLM-written rows: {len(traces) + len(kept)}  ->  reasoning traces: {len(traces)}, kept: {len(kept)}\n")

        print("To delete:")
        for r in traces:
            print(f"  {r[5][:19]}  {r[2]:<10} {one_line(r[3])!r}")
        if args.show_kept:
            print("\nTo keep:")
            for r in kept:
                print(f"  {r[5][:19]}  {r[2]:<10} {one_line(r[3])!r}")

        if not args.apply:
            print("\nDry run only. Review the list above, then re-run with --apply.")
            return 0
        if not traces:
            print("\nNothing to delete.")
            return 0

        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = args.db.with_name(f"{args.db.name}.bak-{stamp}")
        tombstone = args.db.with_name(f"{args.db.stem}.deleted-{stamp}.jsonl")
        if backup.exists() or tombstone.exists():
            print("backup/tombstone file already exists; refusing to overwrite", file=sys.stderr)
            return 2

        # Consistent snapshot even while MCP servers have the db open.
        conn.execute(f"VACUUM INTO '{backup.as_posix()}'")
        print(f"\nbackup:    {backup}")

        with open(tombstone, "w", encoding="utf-8") as fh:
            for r in traces:
                fh.write(json.dumps({
                    "id": r[0], "topic": r[1], "category": r[2],
                    "content": r[3], "metadata_json": r[4], "created_at": r[5],
                }, ensure_ascii=False) + "\n")
        print(f"tombstone: {tombstone}  (embeddings omitted; restore from backup if needed)")

        # Re-select inside the write transaction so rows added since the dry-run
        # listing are judged by the same rules, and delete strictly by id.
        conn.execute("BEGIN IMMEDIATE")
        try:
            ids = [r[0] for r in find_candidates(conn)[0]]
            conn.executemany("DELETE FROM vectors WHERE id = ?", [(i,) for i in ids])
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        remaining = conn.execute("SELECT COUNT(*) FROM vectors").fetchone()[0]
        print(f"deleted {len(ids)} rows; {remaining} remain")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
