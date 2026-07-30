"""Reproduce the notebook's MCD/MVD definition: TRUE labels vs RECOVERED
partition, both within the ORIGINAL dataset. No synthetic data involved."""
import os
for v in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS"): os.environ[v]="1"
import glob, numpy as np, pandas as pd
from scipy.spatial.distance import cdist
from scipy.optimize import linear_sum_assignment
from sklearn.cluster import KMeans, AgglomerativeClustering
from sklearn.preprocessing import StandardScaler
from concurrent.futures import ProcessPoolExecutor

def cents(X, lab):
    return np.array([X[lab==l].mean(axis=0) for l in np.unique(lab)])

def mcd(tc, pc):
    D=cdist(tc,pc); r,c=linear_sum_assignment(D); return D[r,c].mean()

def mvd(X, tl, pl):
    tc={l:X[tl==l].mean(axis=0) for l in np.unique(tl)}
    pc={l:X[pl==l].mean(axis=0) for l in np.unique(pl)}
    D=cdist(np.array(list(tc.values())), np.array(list(pc.values())))
    r,c=linear_sum_assignment(D)
    tk=list(tc); pk=list(pc); ds=[]
    for i,j in zip(r,c):
        vt=np.mean(np.sum((X[tl==tk[i]]-tc[tk[i]])**2,axis=1))
        vp=np.mean(np.sum((X[pl==pk[j]]-pc[pk[j]])**2,axis=1))
        ds.append(abs(vt-vp))
    return float(np.mean(ds))

def one(fp):
    f=os.path.basename(fp).replace('.parquet','').split('_')
    p=int(f[2][1:]); k=int(f[3][1:]); rho=float(f[4][3:]); sep=float(f[5][3:])
    d=pd.read_parquet(fp); d=d[d['rep']==1]
    feats=[c for c in d.columns if c.startswith('X')]
    X=StandardScaler().fit_transform(d[feats].values)
    tl=d['group'].values
    km=KMeans(n_clusters=k,n_init=10,random_state=42).fit_predict(X)
    hc=AgglomerativeClustering(n_clusters=k,linkage='ward').fit_predict(X)
    return dict(p=p,k=k,rho=rho,sep=sep,
                mcd_km=mcd(cents(X,tl),cents(X,km)), mcd_hc=mcd(cents(X,tl),cents(X,hc)),
                mvd_km=mvd(X,tl,km), mvd_hc=mvd(X,tl,hc))

if __name__=="__main__":
    files=sorted(glob.glob("/home/sterry/Desktop/academic/ml-research/clustering/data/original/*.parquet"))
    with ProcessPoolExecutor(max_workers=20) as ex:
        rows=list(ex.map(one, files))
    df=pd.DataFrame(rows)
    print("n files:", len(df))
    print("\nMCD by sep (paper: KM 0.60->0.19, HC 0.85->0.20):")
    print(df.groupby('sep')[['mcd_km','mcd_hc']].mean().round(3).to_string())
    print("\nMVD by p (paper: KM 0.15->0.67, HC 0.25->0.98):")
    print(df.groupby('p')[['mvd_km','mvd_hc']].mean().round(3).to_string())
    print("\nMVD by sep (paper: KM 0.29 at sep2 -> 0.49 at sep10):")
    print(df.groupby('sep')[['mvd_km','mvd_hc']].mean().round(3).to_string())
    df.to_parquet('notebook_metric_check.parquet')
