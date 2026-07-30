"""Filesystem layout, resolved once.

DATA_ROOT is where the generated datasets live. It defaults to the directory
this package sits in, but the datasets are large (2.1 GB) and are typically kept
outside the repo, so override it:

    export SYNTHCLUST_DATA=/path/to/clustering

RESULTS_DIR and FIGURES_DIR are inside the repo and are created on demand.
"""
import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DATA_ROOT = Path(os.environ.get("SYNTHCLUST_DATA", REPO))
ORIGINAL_DIR = DATA_ROOT / "data" / "original"
SYNTHETIC_DIR = DATA_ROOT / "data" / "synthetic"
RESULTS_DIR = REPO / "results"
FIGURES_DIR = REPO / "manuscript" / "figures"
CONFIG = REPO / "config.json"

CLUSTERING_RESULTS = RESULTS_DIR / "clustering_results.parquet"
FIDELITY_RESULTS = RESULTS_DIR / "khat_fidelity_full.parquet"


def require(path: Path, hint: str = "") -> Path:
    """Fail loudly and early rather than deep inside a worker process."""
    if not path.exists():
        msg = f"missing input: {path}"
        if hint:
            msg += f"\n  {hint}"
        raise FileNotFoundError(msg)
    return path
