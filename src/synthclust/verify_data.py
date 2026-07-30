"""Check every parquet dataset is readable and complete; optionally delete bad ones.

    uv run verify-data              # report only
    uv run verify-data --delete     # remove unreadable/short files so a re-run
                                    # regenerates them

Why this exists: the synthesis script skips a task when its output file already
exists. If a run is killed while a worker is mid-write, the partial file satisfies
that check and would be skipped forever, silently poisoning the dataset. Writes
are now atomic (temp + rename), but any file produced before that change, or by
an interrupted third-party copy, can still be truncated.

A file is bad if its parquet footer is unreadable, or its row count is not
N * n_reps as declared by config.json.
"""
import argparse
import json
import sys
from pathlib import Path

import pyarrow.parquet as pq

from synthclust.paths import CONFIG, ORIGINAL_DIR, SYNTHETIC_DIR


def expected_rows() -> int:
    cfg = json.loads(Path(CONFIG).read_text())["simulation"]
    return cfg["N"] * cfg["n"]


def check(path: Path, want_rows: int):
    """Return None if fine, else a reason string."""
    try:
        md = pq.ParquetFile(path).metadata
    except Exception as exc:                       # noqa: BLE001
        return f"unreadable ({type(exc).__name__})"
    if md.num_rows != want_rows:
        return f"{md.num_rows} rows, expected {want_rows}"
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--delete", action="store_true",
                    help="delete bad files so a re-run regenerates them")
    ap.add_argument("--quiet", action="store_true",
                    help="only print the summary line")
    args = ap.parse_args()

    want = expected_rows()
    bad_total = 0
    for d in (ORIGINAL_DIR, SYNTHETIC_DIR):
        files = sorted(d.glob("*.parquet"))
        stray = sorted(d.glob("*.tmp*"))
        if not files and not stray:
            print(f"{d}: empty")
            continue
        bad = []
        for i, f in enumerate(files, 1):
            reason = check(f, want)
            if reason:
                bad.append((f, reason))
            if not args.quiet and (i % 20000 == 0):
                print(f"  {d.name}: {i}/{len(files)}", flush=True)

        print(f"{d.name}: {len(files)} files, {len(bad)} bad, "
              f"{len(stray)} stray temporaries")
        for f, reason in bad[:10]:
            print(f"    {f.name}: {reason}")
        if len(bad) > 10:
            print(f"    ... and {len(bad) - 10} more")

        if args.delete:
            for f, _ in bad:
                f.unlink()
            for f in stray:
                f.unlink()
            if bad or stray:
                print(f"    deleted {len(bad) + len(stray)} file(s) "
                      f"-- re-run the generator to replace them")
        bad_total += len(bad) + len(stray)

    if bad_total and not args.delete:
        print("\nRe-run with --delete to remove them, then re-run the generator.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
