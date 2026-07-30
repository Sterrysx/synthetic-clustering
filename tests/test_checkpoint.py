"""Regression tests for the resume machinery.

    uv run python -m pytest tests/ -q

These lock in the two bugs that broke resume during development:

1. TAG MISMATCH. `recompute_metrics` defines its own `scenario_tag()` (it doubles
   as the OD filename stem, "N1000_p2_k2_rho0_..."), which is NOT the same format
   as `checkpoint.scenario_tag` ("p2_k2_rho0.0_..."). Importing both into one
   module means the local definition shadows the import, and whichever function
   `save()` used had to be the one `has()` used, or resume silently found nothing.
   Each stage must save and look up with a single function.

2. EMPTY SHARDS. `run_unit` returns [] when its input data is missing. Once
   recorded as a completed shard, that scenario is skipped forever and vanishes
   from the merged output.
"""
import re
import tempfile
from pathlib import Path

import pytest

from synthclust.checkpoint import ScenarioStore, scenario_tag


@pytest.fixture
def store():
    return ScenarioStore(Path(tempfile.mkdtemp()), "test")


def test_roundtrip(store):
    tag = scenario_tag(2, 2, 0.0, 0.1, "normal")
    assert not store.has(tag)
    store.save(tag, [{"p": 2, "k": 2, "x": 1.0}])
    assert store.has(tag) and store.count() == 1


def test_merge_concatenates_shards(store):
    store.save(scenario_tag(2, 2, 0.0, 0.1, "normal"), [{"x": 1.0}, {"x": 2.0}])
    store.save(scenario_tag(5, 3, 0.4, 10, "gamma"), [{"x": 9.0}])
    assert sorted(store.load_all()["x"]) == [1.0, 2.0, 9.0]


def test_empty_shard_is_refused(store):
    """Bug 2: an empty result means missing input, not completed work."""
    with pytest.raises(ValueError, match="0 rows"):
        store.save(scenario_tag(2, 2, 0.0, 0.1, "normal"), [])
    assert store.count() == 0          # and nothing was recorded


def test_save_is_atomic_no_temporaries_left(store):
    store.save(scenario_tag(2, 2, 0.0, 0.1, "normal"), [{"x": 1.0}])
    assert list(store.dir.glob("*.tmp*")) == []


def test_stale_temporaries_are_cleared(store):
    (store.dir / "junk.tmp999").write_text("x")
    assert store.clear_stale_temporaries() == 1


def test_discard_removes_directory(store):
    store.save(scenario_tag(2, 2, 0.0, 0.1, "normal"), [{"x": 1.0}])
    store.discard()
    assert not store.dir.exists()


def test_metrics_tag_is_not_shadowed_by_the_import():
    """Bug 1: recompute_metrics must use ONE tag function for save and lookup.

    Its own scenario_tag must remain the OD filename stem, and the module must
    not have imported checkpoint's differently-formatted version over it.
    """
    import synthclust.recompute_metrics as rm

    tag = rm.scenario_tag(2, 2, 0.0, 6, "normal")
    assert tag == "N1000_p2_k2_rho0_sep6_normal"
    assert tag != scenario_tag(2, 2, 0.0, 6, "normal")   # formats do differ
    assert rm.scenario_tag is not scenario_tag           # local one wins


def test_metrics_unit_tag_carries_the_replicate(store):
    """The metrics unit is (scenario, replicate), so its shard key must say which.

    Two replicates of one scenario are separate units and must land on separate
    shards; before the split they shared a key, so a kill mid-scenario lost all
    five. The "_rep" suffix is also what the legacy-shard filter in
    recompute_metrics.main keys off, so its presence is load-bearing.
    """
    import synthclust.recompute_metrics as rm

    a = rm.unit_tag(2, 2, 0.0, 6, "normal", 3)
    b = rm.unit_tag(2, 2, 0.0, 6, "normal", 4)
    assert a == "N1000_p2_k2_rho0_sep6_normal_rep3"
    assert a != b and "_rep" in a
    store.save(a, [{"x": 1.0}])
    assert store.has(a) and not store.has(b)


@pytest.mark.parametrize("filename,expected", [
    ("SD_cart_N1000_p2_k2_rho0_sep0.1_normal_syn1", "p2_k2_rho0_sep0.1_normal"),
    ("SD_cart_N1000_p5_k3_rho0.4_sep2_gamma_syn7", "p5_k3_rho0.4_sep2_gamma"),
    ("SD_cart_N1000_p10_k4_rho0_sep10_normal_syn999", "p10_k4_rho0_sep10_normal"),
])
def test_clustering_task_and_row_keys_agree(filename, expected):
    """The two production key paths must land on the same shard.

    run_clustering derives the key twice from independent sources:
      - resume check: values parsed out of the SD filename by regex
      - flush: values read off a result row, which for a reloaded shard have
        been through pandas and come back as numpy dtypes
    This test builds each side the way production does -- the row side via a real
    DataFrame round-trip -- rather than reusing one dict for both, so a type or
    formatting divergence between the paths would actually fail it.
    """
    import pandas as pd

    sd_re = re.compile(
        r"SD_(\w+?)_N(\d+)_p(\d+)_k(\d+)_rho([\d.]+)_sep([\d.]+)_(\w+?)_syn(\d+)")
    m = sd_re.search(filename)

    # Path A: task built by the regex parse (run_clustering's task dict).
    from_task = scenario_tag(int(m.group(3)), int(m.group(4)), float(m.group(5)),
                             float(m.group(6)), m.group(7))

    # Path B: a worker result row, serialised to a shard and read back, so the
    # values carry numpy dtypes exactly as on a resumed run.
    row = pd.DataFrame([{
        "p": int(m.group(3)), "k": int(m.group(4)),
        "rho": float(m.group(5)), "sep": float(m.group(6)),
        "distribution": m.group(7),
    }]).iloc[0]
    from_row = scenario_tag(row["p"], row["k"], row["rho"], row["sep"],
                            row["distribution"])

    assert from_task == from_row == expected


@pytest.mark.parametrize("a,b", [
    ((2, 2, 0, 2, "normal"), (2, 2, 0.0, 2.0, "normal")),      # int vs float
    ((2, 2, 0.4, 10, "gamma"), (2.0, 2.0, 0.4, 10.0, "gamma")),  # all widened
])
def test_numeric_type_does_not_change_the_key(a, b):
    """sep=2 and sep=2.0 are the same scenario and must share one shard.

    Before canonicalisation these produced "sep2" and "sep2.0": two shards for one
    scenario, so a resume would never match and the merged output would hold
    duplicate rows.
    """
    assert scenario_tag(*a) == scenario_tag(*b)


def test_integral_values_have_no_decimal_point():
    assert scenario_tag(2, 2, 0.0, 10.0, "normal") == "p2_k2_rho0_sep10_normal"
    assert scenario_tag(2, 2, 0.4, 0.1, "normal") == "p2_k2_rho0.4_sep0.1_normal"


def test_stages_use_separate_directories():
    """Differing tag formats are safe only because the shard directories differ."""
    root = Path(tempfile.mkdtemp())
    assert (ScenarioStore(root, "clustering").dir
            != ScenarioStore(root, "metrics").dir)
