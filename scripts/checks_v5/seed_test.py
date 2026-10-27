# MI5: does the shared KMeans random_state=42 (same seed on original and synthetic fits) matter?
# For every scenario, replicate 1, synthetic draws 1..20: recompute k-hat (full range) and MCD/MVD/dG
# for k-means on the synthetic data with independent seeds, and compare with the stored values.
import os, sys, json
for v in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS"): os.environ[v]="1"
REPO="/home/sterry/Desktop/personal/academic/research/synthetic-clustering"
sys.path.insert(0, REPO+"/src")
import numpy as np, pandas as pd, multiprocessing as mp
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score
from scipy.optimize import linear_sum_assignment
import synthclust.recompute_metrics as rm
D=20
def unit(tag):
    od=pd.read_parquet(f"{REPO}/data/original/OD_{tag}.parquet"); feats=[c for c in od if c.startswith("X")]
    k=int(tag.split("_k")[1].split("_")[0])
    Rr=od[od.rep==1]; sc=StandardScaler().fit(Rr[feats].values); Xr=sc.transform(Rr[feats].values)
    lr=rm.fit(Xr,k,"km"); ref=rm.partition_stats(Xr,lr,k)
    rows=[]
    for m in range(1,D+1):
        sd=pd.read_parquet(f"{REPO}/data/synthetic/SD_cart_{tag}_syn{m}.parquet",columns=feats+["rep"])
        Xs=sc.transform(sd[sd.rep==1][feats].values)
        import zlib; seed=int(1e6+zlib.crc32(f"{tag}|{m}".encode())%1000003)
        scan={kk: silhouette_score(Xs, KMeans(kk,n_init=10,random_state=seed+kk).fit_predict(Xs)) for kk in range(2,9)}
        khat=max(scan,key=scan.get)
        ls=KMeans(k,n_init=10,random_state=seed).fit_predict(Xs)
        cs,vs,ss=rm.partition_stats(Xs,ls,k); cr,vr,sr=ref
        cost=np.linalg.norm(cr[:,None,:]-cs[None,:,:],axis=2); ri,ci=linear_sum_assignment(cost)
        rows.append(dict(tag=tag,syn_idx=m,khat_syn_km_full_indep=khat,mcd_km_indep=float(cost[ri,ci].mean()),
                         mvd_km_indep=float(np.mean(np.abs(vr[ri]-vs[ci]))),dgini_km_indep=abs(rm.gini(sr)-rm.gini(ss))))
    return rows
if __name__=="__main__":
    tags=sorted(os.path.basename(f)[3:-8] for f in __import__("glob").glob(f"{REPO}/data/original/OD_*.parquet"))
    with mp.Pool(18) as pool: rows=[r for rs in pool.imap_unordered(unit,tags) for r in rs]
    new=pd.DataFrame(rows)
    st=pd.read_parquet(f"{REPO}/results/khat_fidelity_full.parquet")
    st=st[(st.rep==1)&(st.syn_idx<=D)].copy()
    st["tag"]=st.apply(lambda r: rm.scenario_tag(r.p,r.k,r.rho,r.sep,r.distribution),axis=1)
    mg=st.merge(new,on=["tag","syn_idx"])
    ag_old=(mg.khat_syn_km_full==mg.khat_real_km_full).mean(); ag_new=(mg.khat_syn_km_full_indep==mg.khat_real_km_full).mean()
    out=dict(pairs=len(mg), khat_same=float((mg.khat_syn_km_full==mg.khat_syn_km_full_indep).mean()),
             AG_seed42=float(ag_old), AG_indep=float(ag_new),
             MCD_seed42=float(mg.mcd_km.mean()), MCD_indep=float(mg.mcd_km_indep.mean()),
             MVD_seed42=float(mg.mvd_km.mean()), MVD_indep=float(mg.mvd_km_indep.mean()),
             dG_seed42=float(mg.dgini_km.mean()), dG_indep=float(mg.dgini_km_indep.mean()))
    print(json.dumps(out)); json.dump(out, open("results/logs/v5check_seed_test.json","w"), indent=1)
    mg.to_parquet("results/logs/v5check_seed_test_rows.parquet")
