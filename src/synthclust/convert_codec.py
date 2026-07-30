"""Rewrite the original parquet datasets with a different compression codec.

Workaround for an R `arrow` built without ZSTB support, which fails at read time
with "Support for codec 'zstd' not built". Python's pyarrow ships all codecs, so
this converts the files to something a minimal arrow build can read.

    uv run convert-codec                 # zstd -> uncompressed, in place
    uv run convert-codec --codec snappy
    uv run convert-codec --check         # report codecs, change nothing

Dropping ZSTD costs little disk here, because float64 measurement noise is
close to incompressible. Measured over every file:

    data/original    144 files      38.0 MB -> 39.7 MB   (+4.4%)
    data/synthetic   14,400 files    2.12 GB ->  2.17 GB  (+2.4%)

At m = 1000 the synthetic side projects to 21.2 GB -> 21.8 GB.

(Do not estimate this from an alphabetical head of the file list: "p10" sorts
before "p2" and "p5", so the first files are the widest ones and extrapolating
from them overstates the total.)

Column data and row order are preserved exactly -- only the storage codec
changes. Verified by comparing the reloaded table against the original.
"""
import argparse
import shutil
import sys
import tempfile
from pathlib import Path

import pyarrow.parquet as pq

from synthclust.paths import ORIGINAL_DIR, SYNTHETIC_DIR


def codecs_of(path: Path) -> set[str]:
    md = pq.ParquetFile(path).metadata
    return {
        md.row_group(r).column(c).compression
        for r in range(md.num_row_groups)
        for c in range(md.num_columns)
    }


def convert(path: Path, codec: str) -> bool:
    """Rewrite one file. Returns True if it was changed.

    pyarrow spells "no compression" as "none"; the parquet metadata reports it
    as "UNCOMPRESSED". Both spellings are accepted on the command line.
    """
    write_as = "none" if codec in ("uncompressed", "none") else codec
    target = "UNCOMPRESSED" if write_as == "none" else codec.upper()
    table = pq.read_table(path)
    if codecs_of(path) == {target}:
        return False
    tmp = Path(tempfile.mkstemp(suffix=".parquet", dir=path.parent)[1])
    try:
        pq.write_table(table, tmp, compression=write_as)
        check = pq.read_table(tmp)
        if check.num_rows != table.num_rows or check.schema != table.schema:
            raise RuntimeError(f"verification failed for {path.name}")
        if not check.equals(table):
            raise RuntimeError(f"content differs after rewrite: {path.name}")
        shutil.move(str(tmp), str(path))
    finally:
        tmp.unlink(missing_ok=True)
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--codec", default="uncompressed",
                    choices=["uncompressed", "snappy", "gzip", "zstd"])
    ap.add_argument("--check", action="store_true",
                    help="report current codecs and exit")
    ap.add_argument("--synthetic", action="store_true",
                    help="also convert data/synthetic (slow: many files)")
    args = ap.parse_args()

    dirs = [ORIGINAL_DIR] + ([SYNTHETIC_DIR] if args.synthetic else [])
    for d in dirs:
        files = sorted(d.glob("*.parquet"))
        if not files:
            print(f"{d}: no parquet files")
            continue
        if args.check:
            seen: dict[str, int] = {}
            for f in files:
                for c in codecs_of(f):
                    seen[c] = seen.get(c, 0) + 1
            print(f"{d}: {len(files)} files, codecs {seen}")
            continue
        changed = 0
        for i, f in enumerate(files, 1):
            if convert(f, args.codec):
                changed += 1
            if i % 500 == 0 or i == len(files):
                print(f"  {d.name}: {i}/{len(files)}", flush=True)
        print(f"{d}: {changed} of {len(files)} rewritten as {args.codec}")

    if not args.check:
        print("\nDone. Verify from R:")
        print("  Rscript R/diagnose.R")


if __name__ == "__main__":
    sys.exit(main())
