# 18 concurrent worker processes, each running one model-selection scan (both algorithms),
# with BLAS threads pinned to 1 vs left at the library default.
import os, sys, subprocess, time, json
REPO="/home/sterry/Desktop/personal/academic/research/synthetic-clustering"
child = r'''
import sys; sys.path.insert(0, "%s/src")
import pandas as pd, numpy as np
from sklearn.preprocessing import StandardScaler
from synthclust.recompute_metrics import sil_scan
od=pd.read_parquet("%s/data/original/OD_N1000_p10_k4_rho0.4_sep6_normal.parquet")
X=StandardScaler().fit_transform(od[od.rep==1][[f"X{i}" for i in range(1,11)]].values)
sil_scan(X,"km"); sil_scan(X,"hc")
''' % (REPO, REPO)
def run(pinned):
    env=dict(os.environ)
    for v in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS"):
        if pinned: env[v]="1"
        else: env.pop(v, None)
    t0=time.time()
    ps=[subprocess.Popen([sys.executable,"-c",child],env=env) for _ in range(18)]
    for p in ps: p.wait()
    return time.time()-t0
if __name__=="__main__":
    res={"pinned_s":run(True),"unpinned_s":run(False)}; res["ratio"]=res["unpinned_s"]/res["pinned_s"]
    print(json.dumps(res)); json.dump(res, open("results/logs/v5check_thread_bench.json","w"), indent=1)
