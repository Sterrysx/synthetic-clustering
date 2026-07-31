#!/usr/bin/env python3
# ==============================================================================
# SCRIPT:  03_run_clustering.py
# PURPOSE: Evaluate clustering quality: Original Data vs Synthetic Data.
#          Parallel across 18 cores via multiprocessing.Pool.
#          Each worker streams its own SD file — low per-process memory.
#          Live per-core dashboard updates every 250 ms via monitor thread.
#          Thread pinning: 1 BLAS thread per worker to avoid oversubscription.
# ==============================================================================

import os
# ── CRITICAL: pin BLAS/OpenMP to 1 thread BEFORE importing numpy/sklearn ─────
os.environ["OMP_NUM_THREADS"]       = "1"
os.environ["OPENBLAS_NUM_THREADS"]  = "1"
os.environ["MKL_NUM_THREADS"]       = "1"
os.environ["VECLIB_MAXIMUM_THREADS"]= "1"
os.environ["NUMEXPR_NUM_THREADS"]   = "1"

import json
import re
import glob
import gc
import warnings
import time
import sys
import threading
import multiprocessing as mp
from datetime import datetime, timedelta
from collections import defaultdict

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)

# Worker processes. Defaults to two below the detected core count, leaving room
# for the OS and this process; override with SYNTHCLUST_WORKERS to match your
# machine. See "Adapting the parallelism to your hardware" in the README.
N_WORKERS = int(os.environ.get("SYNTHCLUST_WORKERS",
                               max(1, (os.cpu_count() or 4) - 2)))
_DASH_LINES = N_WORKERS + 3

# ── Terminal Colors ───────────────────────────────────────────────────────────
class Colors:
    HEADER  = '\033[95m'
    BLUE    = '\033[94m'
    CYAN    = '\033[96m'
    GREEN   = '\033[92m'
    WARNING = '\033[93m'
    RED     = '\033[91m'
    ENDC    = '\033[0m'
    BOLD    = '\033[1m'
    DIM     = '\033[2m'

def _ts():
    return datetime.now().strftime('%H:%M:%S')

def log_info(msg):    print(f"{Colors.BLUE}[{_ts()}] INFO:{Colors.ENDC} {msg}", flush=True)
def log_success(msg): print(f"{Colors.GREEN}[{_ts()}] \u2713{Colors.ENDC} {msg}", flush=True)
def log_warn(msg):    print(f"{Colors.WARNING}[{_ts()}] WARN:{Colors.ENDC} {msg}", flush=True)
def log_error(msg):   print(f"{Colors.RED}[{_ts()}] ERROR:{Colors.ENDC} {msg}", flush=True)

# ── Memory Monitor ────────────────────────────────────────────────────────────
def _read_mem():
    info = {"proc_gb": 0.0, "total_gb": 1.0, "avail_gb": 1.0,
            "used_pct": 0.0, "swap_gb": 0.0}
    try:
        with open("/proc/self/status") as f:
            for ln in f:
                if ln.startswith("VmRSS:"):
                    info["proc_gb"] = int(ln.split()[1]) / 1_048_576
    except OSError:
        pass
    try:
        with open("/proc/meminfo") as f:
            kv = {}
            for ln in f:
                parts = ln.split()
                kv[parts[0].rstrip(":")] = int(parts[1])
        info["total_gb"] = kv["MemTotal"]     / 1_048_576
        info["avail_gb"] = kv["MemAvailable"] / 1_048_576
        info["used_pct"] = 100.0 * (1 - kv["MemAvailable"] / kv["MemTotal"])
        st = kv.get("SwapTotal", 0); sf = kv.get("SwapFree", 0)
        info["swap_gb"]  = (st - sf) / 1_048_576
    except OSError:
        pass
    return info

def _mem_bar():
    m = _read_mem()
    bw     = 15
    filled = int(m["used_pct"] / 100 * bw)
    bar    = "\u2588" * filled + "\u2591" * (bw - filled)
    clr    = (Colors.GREEN   if m["used_pct"] < 60 else
              Colors.WARNING if m["used_pct"] < 85 else Colors.RED)
    return (f"{clr}RAM [{bar}] {m['used_pct']:4.1f}%{Colors.ENDC}  "
            f"Proc {m['proc_gb']:.2f} GB  "
            f"Free {m['avail_gb']:.1f}/{m['total_gb']:.1f} GB  "
            f"Swap {m['swap_gb']:.1f} GB")

# ── Live Per-Core Dashboard ───────────────────────────────────────────────────
def _render_dashboard(core_state, tasks_done, total_tasks, total_evals, t0):
    elapsed = time.time() - t0
    pct     = tasks_done / total_tasks * 100 if total_tasks else 0
    rate    = total_evals / elapsed if elapsed > 1e-3 else 0.0
    eta     = (str(timedelta(seconds=int(elapsed / tasks_done * (total_tasks - tasks_done))))
               if tasks_done > 0 and elapsed > 0 else "...")

    bw     = 30
    filled = int(pct / 100 * bw)
    bar    = "\u2588" * filled + "\u2591" * (bw - filled)

    lines = []
    lines.append(
        f"  {Colors.CYAN}[{bar}]{Colors.ENDC} "
        f"{tasks_done}/{total_tasks} files  ({pct:4.1f}%)  "
        f"{total_evals:,} evals  {rate:,.1f} e/s  "
        f"ETA {eta}  ({elapsed:.0f}s)"
    )
    lines.append(f"  {_mem_bar()}")
    lines.append(f"  {Colors.DIM}{'─'*74}{Colors.ENDC}")

    sorted_pids = sorted(core_state.keys())
    for i in range(N_WORKERS):
        idx = i + 1
        if i < len(sorted_pids):
            pid = sorted_pids[i]
            st  = core_state[pid]
            status = st.get("status", "idle")
            fname  = os.path.basename(st.get("file", ""))
            rep    = st.get("rep", 0)
            treps  = st.get("total_reps", 1)

            if status == "idle":
                badge  = f"{Colors.DIM}[IDLE    ]{Colors.ENDC}"
                detail = ""
            elif status == "working":
                badge  = f"{Colors.GREEN}[WORKING ]{Colors.ENDC}"
                rpct   = int(rep / treps * 10) if treps else 0
                rbar   = "\u25a0" * rpct + "\u00b7" * (10 - rpct)
                short  = fname[:38] + "\u2026" if len(fname) > 39 else fname
                detail = f" {rbar}  rep {rep:>2}/{treps}  {Colors.DIM}{short}{Colors.ENDC}"
            else:
                badge  = f"{Colors.DIM}[DONE    ]{Colors.ENDC}"
                detail = f" {Colors.DIM}{fname[:48]}{Colors.ENDC}"
        else:
            badge  = f"{Colors.DIM}[IDLE    ]{Colors.ENDC}"
            detail = ""

        lines.append(f"  Core {idx:>2} {badge}{detail}")

    sys.stdout.write(f"\033[{_DASH_LINES}A")
    for ln in lines:
        sys.stdout.write(f"\033[2K{ln}\n")
    sys.stdout.flush()

# ══════════════════════════════════════════════════════════════════════════════
#  PARALLEL WORKER
# ══════════════════════════════════════════════════════════════════════════════
def _process_one_sd(args):
    """
    Each worker: read one OD + one SD parquet, run clustering per rep,
    push heartbeat messages to queue.

    Thread-pinning env vars are inherited from the parent process (set at
    module top), so sklearn/BLAS uses exactly 1 thread per worker.
    """
    # local imports — safe across fork
    from synthclust.clustering_utils import detect_optimal_k, calculate_quality_metrics
    import numpy as _np
    import pandas as _pd

    task, q = args
    pid     = os.getpid()

    fp      = task["fp"]
    od_fp   = task["od_fp"]
    method  = task["method"]
    N       = task["N"]
    p_val   = task["p"]
    k_truth = task["k"]
    rho     = task["rho"]
    sep     = task["sep"]
    dist    = task["distribution"]
    syn_idx = task["syn_idx"]
    x_cols  = [f"X{i}" for i in range(1, p_val + 1)]

    # k search range: no need to search beyond k_truth + 2, capped at 8
    k_max   = min(k_truth + 3, 8)

    try:
        od_df = _pd.read_parquet(od_fp)
        sd_df = _pd.read_parquet(fp)

        od_groups  = {r: g for r, g in od_df.groupby("rep")}
        sd_groups  = {r: g for r, g in sd_df.groupby("rep")}
        del od_df, sd_df

        total_reps = len(sd_groups)
        q.put({"type": "start", "pid": pid, "file": fp, "total_reps": total_reps})

        rows = []
        for rep_num, (rep_id, sd_grp) in enumerate(sd_groups.items(), 1):
            q.put({"type": "rep", "pid": pid, "rep": rep_num})

            od_grp = od_groups.get(rep_id)
            if od_grp is None:
                continue

            X_od = od_grp[x_cols].to_numpy(dtype=_np.float64)
            X_sd = sd_grp[x_cols].to_numpy(dtype=_np.float64)

            # Pass k_max so detect_optimal_k only searches up to k_truth+3
            k_found_km = detect_optimal_k(X_sd, method='kmeans',      k_max=k_max)
            k_found_hc = detect_optimal_k(X_sd, method='hierarchical', k_max=k_max)

            sil_real_km, dist_real_km = calculate_quality_metrics(X_od, k_truth, 'kmeans')
            sil_real_hc, dist_real_hc = calculate_quality_metrics(X_od, k_truth, 'hierarchical')
            sil_syn_km,  dist_syn_km  = calculate_quality_metrics(X_sd, k_truth, 'kmeans')
            sil_syn_hc,  dist_syn_hc  = calculate_quality_metrics(X_sd, k_truth, 'hierarchical')

            rows.append({
                "method": method, "N": N, "p": p_val, "k": k_truth,
                "rho": rho, "sep": sep, "distribution": dist,
                "rep": int(rep_id), "syn_idx": syn_idx,
                "success_kmeans": 1 if k_found_km == k_truth else 0,
                "success_hc":     1 if k_found_hc == k_truth else 0,
                "diff_sil_km":    sil_syn_km  - sil_real_km,
                "diff_sil_hc":    sil_syn_hc  - sil_real_hc,
                "diff_dist_km":   dist_syn_km - dist_real_km,
                "diff_dist_hc":   dist_syn_hc - dist_real_hc,
                "sil_real_km":  sil_real_km,  "sil_syn_km":  sil_syn_km,
                "sil_real_hc":  sil_real_hc,  "sil_syn_hc":  sil_syn_hc,
                "dist_real_km": dist_real_km, "dist_syn_km": dist_syn_km,
                "dist_real_hc": dist_real_hc, "dist_syn_hc": dist_syn_hc,
            })

        q.put({"type": "finish", "pid": pid, "rows": rows})

    except Exception as exc:
        import traceback
        q.put({"type": "error", "pid": pid,
               "msg": f"{os.path.basename(fp)}: {exc}\n{traceback.format_exc()}"})

# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════
def main():

    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*78}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}"
          f"   PARALLEL CLUSTERING EVALUATION PIPELINE  ({N_WORKERS} cores)"
          f"{'':18}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*78}{Colors.ENDC}")
    print(f"{Colors.DIM}NumPy {np.__version__}  \u2022  pandas {pd.__version__}{Colors.ENDC}")
    print(f"  {_mem_bar()}\n")

    # ── Config & Paths ────────────────────────────────────────────────────────
    from synthclust.paths import CONFIG, ORIGINAL_DIR, SYNTHETIC_DIR, RESULTS_DIR
    with open(CONFIG) as f:
        config = json.load(f)

    k_values = config["parameters"]["k"]
    k_global_max = min(max(k_values) + 3, 8)
    log_info(f"k search range: 2 .. {k_global_max}  "
             f"(config k_max={max(k_values)}, capped at 8)")

    od_dir     = str(ORIGINAL_DIR)
    sd_dir     = str(SYNTHETIC_DIR)
    result_dir = str(RESULTS_DIR)
    os.makedirs(result_dir, exist_ok=True)

    _OD_RE = re.compile(
        r"OD_N(\d+)_p(\d+)_k(\d+)_rho([\d.]+)_sep([\d.]+)_([\w]+)\.parquet$")
    _SD_RE = re.compile(
        r"SD_(\w+?)_N(\d+)_p(\d+)_k(\d+)_rho([\d.]+)_sep([\d.]+)_([\w]+)_syn(\d+)\.parquet$")

    # ── Scan directories ──────────────────────────────────────────────────────
    log_info("Scanning data directories \u2026")
    od_files = sorted(glob.glob(os.path.join(od_dir, "OD_*.parquet")))
    sd_files = sorted(glob.glob(os.path.join(sd_dir, "SD_*.parquet")))

    if not od_files:
        log_error(f"No OD parquet files found in {od_dir}"); sys.exit(1)
    if not sd_files:
        log_error(f"No SD parquet files found in {sd_dir}"); sys.exit(1)

    od_map = {}
    for fp in od_files:
        m = _OD_RE.search(os.path.basename(fp))
        if m:
            od_map[(m.group(1), m.group(2), m.group(3),
                    m.group(4), m.group(5), m.group(6))] = fp

    log_success(f"Found {len(od_files)} OD + {len(sd_files)} SD files  "
                f"({len(od_map)} unique OD scenarios)")

    # ── Build task list ───────────────────────────────────────────────────────
    sd_tasks = []
    skipped_files = 0
    for fp in sd_files:
        m = _SD_RE.search(os.path.basename(fp))
        if not m:
            log_warn(f"Regex skip: {os.path.basename(fp)}")
            skipped_files += 1
            continue
        od_key = (m.group(2), m.group(3), m.group(4),
                  m.group(5), m.group(6), m.group(7))
        if od_key not in od_map:
            skipped_files += 1
            continue
        sd_tasks.append({
            "fp":           fp,
            "method":       m.group(1),
            "N":            int(m.group(2)),
            "p":            int(m.group(3)),
            "k":            int(m.group(4)),
            "rho":          float(m.group(5)),
            "sep":          float(m.group(6)),
            "distribution": m.group(7),
            "syn_idx":      int(m.group(8)),
            "od_fp":        od_map[od_key],
        })

    # ── Resume: drop scenarios already checkpointed ───────────────────────────
    # Shards are keyed by design scenario, not by SD file: 144 shards rather
    # than 144,000, and each is written only once its whole scenario is done.
    from synthclust.checkpoint import ScenarioStore, scenario_tag
    store = ScenarioStore(RESULTS_DIR, "clustering")
    if "--restart" in sys.argv:
        store.discard()
        store = ScenarioStore(RESULTS_DIR, "clustering")
    stale = store.clear_stale_temporaries()
    if stale:
        log_warn(f"Cleared {stale} stale temporary shard(s)")

    def _tag_of(t):
        return scenario_tag(t["p"], t["k"], t["rho"], t["sep"], t["distribution"])

    scen_tags = {_tag_of(t) for t in sd_tasks}
    done_tags = {tag for tag in scen_tags if store.has(tag)}
    if done_tags:
        log_success(f"Resuming: {len(done_tags)}/{len(scen_tags)} scenarios "
                    f"already checkpointed, skipping them")
        sd_tasks = [t for t in sd_tasks if _tag_of(t) not in done_tags]

    total_tasks = len(sd_tasks)
    log_info(f"{total_tasks} SD files to process ({skipped_files} skipped)  |  "
             f"{N_WORKERS} worker processes")
    if skipped_files:
        log_warn(f"Skipped {skipped_files} SD file(s) — missing OD match or bad filename")

    # ── Shared queue + state ──────────────────────────────────────────────────
    manager    = mp.Manager()
    q          = manager.Queue()
    core_state = defaultdict(lambda: {"status": "idle", "file": "",
                                      "rep": 0, "total_reps": 0})

    # Use single-element lists so the monitor thread can mutate them
    # (nonlocal doesn't work inside an if-__main__ block)
    tasks_done  = [0]
    total_evals = [0]
    all_results = []
    errors      = []
    t_global    = time.time()

    # Per-scenario checkpoint bookkeeping.
    #   remaining[tag] : SD files still outstanding for that scenario
    #   pending[tag]   : rows accumulated so far, flushed when remaining hits 0
    #   err_tags       : SD basename -> tag, to attribute a failed task
    remaining = defaultdict(int)
    pending   = defaultdict(list)
    err_tags  = {}
    flushed   = [0]
    for t in sd_tasks:
        tag = _tag_of(t)
        remaining[tag] += 1
        err_tags[os.path.basename(t["fp"])] = tag

    log_info(f"Dispatching {total_tasks} SD files across {N_WORKERS} cores \u2026")
    for _ in range(_DASH_LINES):
        print()

    # ── Monitor thread ────────────────────────────────────────────────────────
    _done_event = threading.Event()

    def _monitor():
        while not _done_event.is_set() or not q.empty():
            while True:
                try:
                    msg = q.get_nowait()
                except Exception:
                    break

                mtype = msg["type"]
                pid   = msg["pid"]

                if mtype == "start":
                    core_state[pid].update({
                        "status":     "working",
                        "file":       msg["file"],
                        "rep":        0,
                        "total_reps": msg["total_reps"],
                    })
                elif mtype == "rep":
                    core_state[pid]["rep"] = msg["rep"]
                elif mtype == "finish":
                    tasks_done[0]  += 1
                    total_evals[0] += len(msg["rows"])
                    # Bucket by scenario, and checkpoint a scenario the moment
                    # its last SD file lands. A kill then costs only the
                    # scenarios still in flight, not the whole stage.
                    # `remaining` counts TASKS (SD files) per scenario, so it is
                    # decremented once per finish message, not once per row.
                    if msg["rows"]:
                        r0 = msg["rows"][0]
                        tag = scenario_tag(r0["p"], r0["k"], r0["rho"],
                                           r0["sep"], r0["distribution"])
                        pending[tag].extend(msg["rows"])
                        remaining[tag] -= 1
                        if remaining[tag] <= 0:
                            rows_out = pending.pop(tag, [])
                            if rows_out:          # never checkpoint an empty shard
                                store.save(tag, rows_out)
                                flushed[0] += 1
                    core_state[pid].update({
                        "status": "done",
                        "rep":    core_state[pid]["total_reps"],
                    })
                elif mtype == "error":
                    errors.append(msg["msg"])
                    core_state[pid]["status"] = "done"
                    tasks_done[0] += 1
                    # A failed task still consumed a slot in its scenario. The
                    # tag is recovered from the filename, since no rows came
                    # back. Without this the scenario never reaches zero and is
                    # never checkpointed.
                    tag = err_tags.get(msg["msg"].split(":")[0])
                    if tag is not None:
                        remaining[tag] -= 1
                        if remaining[tag] <= 0:
                            rows_out = pending.pop(tag, [])
                            if rows_out:      # never checkpoint an empty shard
                                store.save(tag, rows_out)
                                flushed[0] += 1

            _render_dashboard(core_state, tasks_done[0], total_tasks,
                              total_evals[0], t_global)
            time.sleep(0.25)

    monitor_thread = threading.Thread(target=_monitor, daemon=True)
    monitor_thread.start()

    # ── Pool ──────────────────────────────────────────────────────────────────
    pool_args = [(task, q) for task in sd_tasks]
    with mp.Pool(processes=N_WORKERS) as pool:
        pool.map(_process_one_sd, pool_args)

    _done_event.set()
    monitor_thread.join(timeout=3)
    _render_dashboard(core_state, tasks_done[0], total_tasks, total_evals[0], t_global)
    print()

    # ── Report ────────────────────────────────────────────────────────────────
    elapsed = time.time() - t_global
    if errors:
        log_warn(f"{len(errors)} task(s) failed:")
        for e in errors[:5]:
            log_error(f"  {e}")

    log_success(f"Completed {total_evals[0]:,} evaluations in {elapsed:.1f}s "
                f"({total_evals[0] / max(elapsed, 1e-9):,.0f} evals/sec)")

    # ── Save ──────────────────────────────────────────────────────────────────
    # Flush any scenario left incomplete (only happens if tasks errored), then
    # merge every shard -- including those written by earlier interrupted runs.
    for tag, rows in list(pending.items()):
        if rows:
            store.save(tag, rows)
            flushed[0] += 1
    pending.clear()

    log_info(f"Checkpointed {flushed[0]} scenario(s) this run; "
             f"{store.count()} shard(s) on disk")
    log_info("Merging shards \u2026")
    df = store.load_all()
    del all_results
    gc.collect()
    if len(df) == 0:
        log_error("no rows produced; leaving previous results untouched")
        return

    parquet_path = os.path.join(result_dir, "clustering_results.parquet")
    csv_path     = os.path.join(result_dir, "clustering_results.csv")

    df.to_parquet(parquet_path, index=False, engine="pyarrow")
    df.to_csv(csv_path, index=False)

    log_success(f"Saved \u2192 {parquet_path}  ({os.path.getsize(parquet_path)/1e6:.1f} MB)")
    log_success(f"Saved \u2192 {csv_path}  ({os.path.getsize(csv_path)/1e6:.1f} MB)")

    # Only drop the shards once every scenario is represented. If tasks errored, the
    # merge above is partial, and discarding would delete the completed scenarios
    # too -- forcing a full recompute of a stage that is hours long.
    if store.count() >= len(scen_tags):
        store.discard()
    else:
        log_warn(f"Merged {store.count()}/{len(scen_tags)} scenarios; keeping shards "
                 f"so a rerun completes the rest")
    print(f"\n  {_mem_bar()}")
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*78}{Colors.ENDC}\n")


if __name__ == "__main__":
    main()
