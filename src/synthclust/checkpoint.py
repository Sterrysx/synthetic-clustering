"""Per-scenario checkpointing, so a killed analysis stage resumes instead of restarting.

Both analysis stages are embarrassingly parallel over the 144 design scenarios.
Each scenario's rows are written to their own parquet under a `.partial_<stage>`
directory as soon as that scenario finishes. A restart reads whatever is already
there and computes only the missing scenarios; the final result is the
concatenation.

Writes are atomic (temp + os.replace), so killing the process mid-write cannot
leave a partial file that a later run would mistake for a finished scenario.

The partial directory is removed once the merged output is written, so a
successful run leaves no clutter.
"""
import os
import shutil
from pathlib import Path

import pandas as pd


def _num(v) -> str:
    """Canonical string for a numeric key component.

    The two key-construction paths in run_clustering reach here with values of
    different provenance: parsed from a filename via float() when building tasks,
    and read back off a DataFrame (numpy dtypes) when a shard is reloaded. Without
    canonicalisation, sep=2 and sep=2.0 would produce "sep2" and "sep2.0" -- two
    shards for one scenario, and a resume that never matches. Integral values are
    rendered without a decimal point; others keep minimal repr.
    """
    f = float(v)
    return str(int(f)) if f.is_integer() else repr(f)


def scenario_tag(p, k, rho, sep, dist) -> str:
    """Filename-safe identifier for one design cell.

    Numeric components are canonicalised, so int/float and python/numpy variants
    of the same value all map to one key.
    """
    return (f"p{_num(p)}_k{_num(k)}_rho{_num(rho)}"
            f"_sep{_num(sep)}_{dist}")


class ScenarioStore:
    """Directory of per-scenario parquet shards."""

    def __init__(self, results_dir, stage: str):
        self.dir = Path(results_dir) / f".partial_{stage}"
        self.dir.mkdir(parents=True, exist_ok=True)

    def path(self, tag: str) -> Path:
        return self.dir / f"{tag}.parquet"

    def has(self, tag: str) -> bool:
        return self.path(tag).exists()

    def save(self, tag: str, rows) -> None:
        """Write one scenario's rows atomically.

        Refuses to record an EMPTY result. An empty row list means the inputs
        were missing (e.g. synthesis had not produced that scenario's SD files
        yet), not that the scenario is finished -- checkpointing it would make a
        restart skip it forever and silently drop it from the merged output.
        """
        if len(rows) == 0:
            raise ValueError(
                f"refusing to checkpoint scenario {tag!r} with 0 rows: "
                "its input data is probably missing"
            )
        target = self.path(tag)
        tmp = target.with_suffix(f".tmp{os.getpid()}")
        pd.DataFrame(rows).to_parquet(tmp, index=False)
        os.replace(tmp, target)

    def load_all(self) -> pd.DataFrame:
        shards = sorted(self.dir.glob("*.parquet"))
        if not shards:
            return pd.DataFrame()
        frames = [pd.read_parquet(s) for s in shards]
        frames = [f for f in frames if not f.empty]
        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, ignore_index=True)

    def count(self) -> int:
        return len(list(self.dir.glob("*.parquet")))

    def clear_stale_temporaries(self) -> int:
        n = 0
        for f in self.dir.glob("*.tmp*"):
            f.unlink()
            n += 1
        return n

    def discard(self) -> None:
        """Remove the shard directory after a successful merge."""
        shutil.rmtree(self.dir, ignore_errors=True)
