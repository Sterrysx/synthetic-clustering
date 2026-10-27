import os, sys, glob, random, time, json
for v in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS"): os.environ[v]="1"
REPO="/home/sterry/Desktop/personal/academic/research/synthetic-clustering"
sys.path.insert(0, REPO+"/src"); sys.path.insert(0, REPO+"/scripts")
import multiprocessing as mp
import time_clustering as tc
if __name__=="__main__":
    files=sorted(glob.glob(REPO+"/data/synthetic/*.parquet")); random.Random(20260929).shuffle(files)
    sample=files[:3000]
    t0=time.time()
    with mp.Pool(18) as pool: ev=sum(pool.imap_unordered(tc.time_one, sample, chunksize=16))
    el=time.time()-t0
    out=dict(sample_files=len(sample), total_files=len(files), evaluations=ev, wall_s=el,
             extrapolated_h=el*len(files)/len(sample)/3600, workers=18)
    print(json.dumps(out)); json.dump(out, open("results/logs/v5check_clustering_timing_sample.json","w"), indent=1)
