"""
Purpose: Drive the 7-phase pipeline with per-phase progress + ETA, resumable at any point.
Usage:   uv run python scripts/pipeline.py [--watch] [--from N]
Author:  Oriol Farrés
Date:    2026-07-30

Every phase reports both its progress and its doneness from disk alone, so the run
can be killed at any moment and continued by relaunching, and a second terminal can
attach read-only with --watch while it runs.

Child stdout goes to results/logs/NN_<phase>.log rather than the terminal: two
stages draw their own ANSI dashboards (run_clustering._render_dashboard and the
per-core block in R/generate_synthetic.R) and those escape codes would shred a Rich
Live region. The bar's tail row shows each log's last line.

Stopping: each stage runs in its own session, and Ctrl-C here SIGTERMs that whole
process group before re-raising. Stages are invoked through .venv/bin directly
rather than `uv run` for the same reason -- uv puts its child in a separate group,
so a terminal SIGINT reached this orchestrator but left a 20-worker pool running
detached, which is how two concurrent runs once ended up sharing 24 cores.
"""
import argparse
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
from math import ceil
from pathlib import Path
from typing import Callable, NamedTuple, Optional

from rich.console import Console
from rich.live import Live
from rich.progress import (BarColumn, MofNCompleteColumn, Progress, ProgressColumn,
                           SpinnerColumn, TaskProgressColumn, TextColumn,
                           TimeElapsedColumn)
from rich.table import Table
from rich.text import Text

from synthclust.paths import (CLUSTERING_RESULTS, CONFIG, FIDELITY_RESULTS,
                              FIGURES_DIR, ORIGINAL_DIR, REPO, RESULTS_DIR,
                              SYNTHETIC_DIR)

_CONSOLE = Console(highlight=False)
_RULE    = "#004D98"
_ANSI    = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
LOG_DIR  = RESULTS_DIR / "logs"
MANU     = REPO / "manuscript"
BIN      = REPO / ".venv" / "bin"         # console scripts, installed by `uv sync`
UV       = "uv"

_cfg   = json.loads(CONFIG.read_text())["simulation"]
M      = _cfg["m"]
N_OD   = 144
N_SD   = N_OD * M
N_UNIT = N_OD * _cfg["n"]                 # metrics unit = (scenario, replicate)
STAMP  = RESULTS_DIR / f".design-m{M}"
FIG_STEMS = ("fig_fidelity", "fig_recovery", "figS_heatmap", "fig_distribution",
             "fig_balance", "fig_normal", "fig_gamma")
N_FIG  = 2 * len(FIG_STEMS) + 1           # pdf + png each, plus supp_table.tex
_STAGE = {4: "clustering", 5: "metrics"}  # phases whose progress is shard-backed


# ── Probes ───────────────────────────────────────────────────────────────────

def _n(d: Path, pat: str = "*.parquet") -> int:
    return sum(1 for _ in d.glob(pat)) if d.exists() else 0


def _shards(stage: str) -> int:
    # Globbed directly rather than through ScenarioStore.count(): that constructor
    # mkdir()s the shard directory, and --watch must never write.
    return _n(RESULTS_DIR / f".partial_{stage}")


def _fresh(out: Path, src: Path) -> bool:
    """True when `out` exists and is no older than `src` — make's own guard."""
    return out.exists() and src.exists() and out.stat().st_mtime >= src.stat().st_mtime


def _figs() -> int:
    n = sum((FIGURES_DIR / f"{s}{e}").exists()
            for s in FIG_STEMS for e in (".pdf", ".png"))
    return n + (MANU / "supp_table.tex").exists()


def _pdfs() -> int:
    return sum((MANU / f"{d}.pdf").exists() for d in ("main", "supplementary"))


# ── Phase table ──────────────────────────────────────────────────────────────

class Phase(NamedTuple):
    title:  str
    unit:   str
    cmds:   list
    total:  Optional[int]                 # None → spinner, no ETA
    count:  Callable[[], int]
    done:   Callable[[], bool]
    always: bool = False                  # run even when done() (idempotent setup)


PHASES = [
    # --extra dev: a bare `uv sync` prunes anything outside the default
    # dependency set, which uninstalled pytest on every run and broke `make test`.
    Phase("Environment", "",
          [["Rscript", str(REPO / "R/setup.R")], [UV, "sync", "--extra", "dev"]],
          None, lambda: 0, lambda: (REPO / ".venv").exists(), always=True),
    Phase("Original data", "files", [["Rscript", str(REPO / "R/generate_original.R")]],
          N_OD, lambda: _n(ORIGINAL_DIR), lambda: _n(ORIGINAL_DIR) >= N_OD),
    Phase("Synthetic data", "files", [["Rscript", str(REPO / "R/generate_synthetic.R")]],
          N_SD, lambda: _n(SYNTHETIC_DIR), lambda: _n(SYNTHETIC_DIR) >= N_SD),
    Phase("Clustering", "scenarios", [[str(BIN / "run-clustering")]],
          N_OD, lambda: _shards("clustering"),
          lambda: _fresh(CLUSTERING_RESULTS, STAMP)),
    Phase("Fidelity metrics", "units", [[str(BIN / "recompute-metrics")]],
          N_UNIT, lambda: _shards("metrics"),
          lambda: _fresh(FIDELITY_RESULTS, CLUSTERING_RESULTS)),
    Phase("Figures", "files",
          [[str(BIN / "make-supp-table")], [str(BIN / "make-figures")]],
          N_FIG, _figs,
          lambda: _figs() >= N_FIG and _fresh(FIGURES_DIR / "fig_fidelity.pdf",
                                              FIDELITY_RESULTS)),
    Phase("Manuscript", "PDFs", [[str(MANU / "build.sh"), "main"],
                                 [str(MANU / "build.sh"), "supplementary"]],
          2, _pdfs,
          lambda: _pdfs() >= 2 and _fresh(MANU / "main.pdf",
                                          FIGURES_DIR / "fig_fidelity.pdf")),
]


# ── ETA ──────────────────────────────────────────────────────────────────────
# Ported from markov-tfg services/serving/main.py:85-93,846-893. Deliberately not
# Rich's TimeRemainingColumn: the estimate comes from the global average, which is
# what holds up over a stage whose units are minutes long.
#
# One difference from the source, forced by resume: `completed` starts at whatever
# was already on disk while `elapsed` starts at zero, so the average must be taken
# over units finished THIS run. That baseline rides along as a task field.

def fmt_duration(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m:02d}m {s:02d}s"
    if m:
        return f"{m}m {s:02d}s"
    return f"{s}s"


def avg_seconds(elapsed: Optional[float], completed: float) -> Optional[float]:
    if elapsed is None or completed <= 0:
        return None
    return elapsed / completed


def remaining_seconds(total, completed, avg_s) -> Optional[int]:
    if total is None or avg_s is None:
        return None
    return ceil(max(total - completed, 0.0) * avg_s)


def _this_run(task) -> float:
    return task.completed - task.fields.get("base", 0)


class AverageEtaColumn(ProgressColumn):
    def render(self, task) -> Text:
        if task.total is None:
            return Text("", style="progress.remaining")
        eta = remaining_seconds(task.total, task.completed,
                                avg_seconds(task.elapsed, _this_run(task)))
        if eta is None:
            return Text("-:--:--", style="progress.remaining")
        m, s = divmod(int(eta), 60)
        h, m = divmod(m, 60)
        return Text(f"{h:d}:{m:02d}:{s:02d}", style="progress.remaining")


class AverageUnitColumn(ProgressColumn):
    def __init__(self, unit: str):
        super().__init__()
        self.unit = unit

    def render(self, task) -> Text:
        avg_s = avg_seconds(task.elapsed, _this_run(task))
        if avg_s is None:
            return Text(f"-- s/{self.unit}", style="dim")
        return Text(f"{avg_s:.2f} s/{self.unit}", style="green")


# ── Rendering ────────────────────────────────────────────────────────────────

def print_phase_header(phase: str, title: str) -> None:
    _CONSOLE.print()
    _CONSOLE.rule(f"[bold white]{phase}  {title}[/]", style=_RULE)


def meta(rows) -> Table:
    t = Table(show_header=False, box=None, padding=(0, 1))
    t.add_column(style="dim", no_wrap=True)
    t.add_column(no_wrap=True)
    for k, v in rows:
        t.add_row(k, str(v))
    return t


def columns(ph: Phase):
    tail_col = TextColumn("[dim]{task.description}")
    if ph.total is None:
        return (SpinnerColumn(), TimeElapsedColumn(), tail_col)
    return (SpinnerColumn(), MofNCompleteColumn(), BarColumn(), TaskProgressColumn(),
            TimeElapsedColumn(), AverageEtaColumn(), AverageUnitColumn(ph.unit),
            tail_col)


def tail(log: Path, width: int = 56) -> str:
    """Last non-blank line of a log, ANSI stripped. Reads only the final 4 KiB."""
    try:
        with log.open("rb") as fh:
            fh.seek(0, 2)
            fh.seek(max(0, fh.tell() - 4096))
            blob = fh.read().decode("utf-8", "replace")
    except OSError:
        return ""
    lines = [ln for ln in _ANSI.sub("", blob).splitlines() if ln.strip()]
    return lines[-1].strip()[-width:] if lines else ""


# ── Run one phase ────────────────────────────────────────────────────────────

def run_phase(i: int, ph: Phase) -> None:
    """Run every command of one phase, polling its progress off disk.

    PRE:  ph.cmds is a non-empty list of argv lists; LOG_DIR exists
    POST: returns only if all commands exited 0; raises SystemExit otherwise.
          Whatever the phase checkpointed before a failure stays on disk.
    """
    log = LOG_DIR / f"{i:02d}_{ph.title.split()[0].lower()}.log"
    base = ph.count() if ph.total else 0
    print_phase_header(f"{i}/{len(PHASES)}", ph.title)
    _CONSOLE.print(meta([("resuming at", f"{base}/{ph.total} {ph.unit}") if base else
                         ("units", f"{ph.total} {ph.unit}" if ph.total else "n/a"),
                         ("log", log)]))

    with Progress(*columns(ph), console=_CONSOLE, refresh_per_second=1) as prog:
        task = prog.add_task("", total=ph.total, completed=base, base=base)
        stop = threading.Event()
        poll = threading.Thread(target=_poll, args=(prog, task, ph, log, stop),
                                daemon=True)
        poll.start()
        try:
            for cmd in ph.cmds:
                rc = _spawn(cmd, log)
                if rc != 0:
                    raise SystemExit(f"phase {i}/{len(PHASES)} {ph.title!r} failed "
                                     f"(exit {rc}) — see {log}")
        finally:
            stop.set()
            poll.join(timeout=2)
            if ph.total:
                prog.update(task, completed=ph.count())


def _poll(prog, task, ph: Phase, log: Path, stop: threading.Event) -> None:
    while not stop.wait(1.0):
        fields = {"completed": ph.count()} if ph.total else {}
        prog.update(task, description=tail(log), **fields)


def _spawn(cmd: list, log: Path) -> int:
    """Run one command to completion, appending its output to `log`.

    PRE:  cmd is an argv list; log's parent exists
    POST: returns the exit status. On ANY exception -- Ctrl-C included -- the whole
          child process group is torn down before re-raising, so no worker pool is
          ever left running detached.
    """
    with log.open("ab") as fh:
        proc = subprocess.Popen(cmd, cwd=REPO, stdout=fh,
                                stderr=subprocess.STDOUT, start_new_session=True)
    try:
        return proc.wait()
    except BaseException:
        _kill_group(proc.pid, signal.SIGTERM)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            _kill_group(proc.pid, signal.SIGKILL)
        raise


def _kill_group(pid: int, sig: int) -> None:
    """Signal a child and every descendant sharing its group.

    PRE:  pid was started with start_new_session=True, so pid == its group id
    POST: sig delivered to the group, or nothing if it has already exited
    """
    try:
        os.killpg(pid, sig)
    except (ProcessLookupError, PermissionError):
        pass


# ── Watch (read-only) ────────────────────────────────────────────────────────

def _shard_rate(stage: Optional[str]) -> Optional[float]:
    """Units per second from the spread of shard mtimes already on disk.

    This is what lets a watcher that just attached show a real ETA instead of
    waiting to observe a completion itself.
    """
    if stage is None:
        return None
    d = RESULTS_DIR / f".partial_{stage}"
    ts = sorted(p.stat().st_mtime for p in d.glob("*.parquet")) if d.exists() else []
    span = ts[-1] - ts[0] if len(ts) >= 2 else 0
    return (len(ts) - 1) / span if span > 0 else None


def _watch_eta(seen: dict, i: int, ph: Phase, n: int) -> str:
    rate = _shard_rate(_STAGE.get(i))
    if rate is None:
        t = time.time()
        t0, n0 = seen.setdefault(i, (t, n))
        rate = (n - n0) / (t - t0) if n > n0 and t > t0 else None
    if not rate:
        return "[dim]-:--:--[/]"
    return f"eta {fmt_duration((ph.total - n) / rate)}"


def watch() -> None:
    """Render phase state from disk until every phase is done. Never writes.

    PRE:  nothing — the pipeline may or may not be running
    POST: returns when all phases report done; Ctrl-C detaches without effect
    """
    seen: dict = {}
    with Live(console=_CONSOLE, refresh_per_second=1) as live:
        while True:
            state = [(ph, ph.done(), ph.count() if ph.total else 0) for ph in PHASES]
            active = next((i for i, (_, d, _) in enumerate(state, 1) if not d), None)
            tbl = Table(show_header=False, box=None, padding=(0, 1))
            for just in ("left", "left", "left", "right", "left"):
                tbl.add_column(justify=just, no_wrap=True)
            for i, (ph, is_done, n) in enumerate(state, 1):
                label = f"{i}/{len(PHASES)}"
                if is_done:
                    tbl.add_row(label, ph.title, "[green]done[/]", "", "")
                elif i == active:
                    tbl.add_row(label, f"[bold]{ph.title}[/]", "[yellow]running[/]",
                                f"{n}/{ph.total}" if ph.total else "",
                                _watch_eta(seen, i, ph, n) if ph.total else "")
                else:
                    tbl.add_row(label, f"[dim]{ph.title}[/]", "[dim]pending[/]", "", "")
            live.update(tbl)
            if active is None:
                return
            time.sleep(1)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--watch", action="store_true",
                    help="read-only: render phase state from disk, then exit")
    ap.add_argument("--from", dest="start", type=int, default=1, metavar="N",
                    help=f"start at phase N (1-{len(PHASES)})")
    args = ap.parse_args()
    if args.watch:
        return watch()

    # 1. Banner
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    _CONSOLE.print(meta([("design", f"m = {M}"), ("phases", len(PHASES)),
                         ("logs", LOG_DIR)]))

    # 2. Walk the phases, skipping whatever disk already says is done
    t0 = time.time()
    for i, ph in enumerate(PHASES, 1):
        if i < args.start:
            continue
        if ph.done() and not ph.always:
            print_phase_header(f"{i}/{len(PHASES)}", ph.title)
            _CONSOLE.print(meta([("status", "[green]done[/] — skipping")]))
            continue
        run_phase(i, ph)

    # 3. Summary
    _CONSOLE.print()
    _CONSOLE.rule(f"[bold green]Pipeline complete   m = {M}   "
                  f"{fmt_duration(time.time() - t0)}[/]", style=_RULE)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        _CONSOLE.print("\n[yellow]stopped[/] — checkpoints kept; rerun to continue")
        sys.exit(130)
