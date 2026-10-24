"""Leakage-safe WR role-aware PPR challenger on 2025 historical player-weeks.
Diagnostic only: no live model or site changes.
"""
from pathlib import Path
import numpy as np
import pandas as pd
P=Path("projection-model/2025-historical-ppr-dataset.csv")
d=pd.read_csv(P,low_memory=False)
print("Available columns:",list(d.columns))
d=d[d.position.eq("WR")].copy()
needed=["week","actual_ppr","opportunity_score","production_score","usage_score","redzone_score","model_confidence_score"]
if any(x not in d for x in needed):raise RuntimeError("Missing model features")
ids=next((c for c in ("player_id","player_name","player_display_name") if c in d),None)
if not ids:raise RuntimeError("Missing player identifier")
d["week"]=pd.to_numeric(d.week,errors="coerce")
for c in needed[1:]:d[c]=pd.to_numeric(d[c],errors="coerce")
d=d.dropna(subset=needed).sort_values(["week",ids]).copy()
# Role prior uses strictly earlier weeks, never same-week target.
d["prior_games"]=d.groupby(ids)["actual_ppr"].transform(lambda s:s.shift().expanding().count())
d["role_prior_ppr"]=d.groupby(ids)["actual_ppr"].transform(lambda s:s.shift().rolling(5,min_periods=1).mean())
features=needed[2:]
out=[]
for w in sorted(d.week.unique()):
    train=d[d.week<w];test=d[d.week==w]
    if len(train)<80 or len(test)<8:continue
    x=np.column_stack([np.ones(len(train)),train[features].to_numpy(float)])
    xt=np.column_stack([np.ones(len(test)),test[features].to_numpy(float)])
    beta=np.linalg.lstsq(x,train.actual_ppr.to_numpy(float),rcond=None)[0]
    baseline=xt@beta
    # Shrink toward role prior only where >=3 prior games exist; shrinkage is precommitted, not tuned.
    prior=test.role_prior_ppr.to_numpy(float)
    eligible=(test.prior_games.to_numpy(float)>=3)&np.isfinite(prior)
    for weight in (0,.15,.30):
        pred=baseline.copy()
        pred[eligible]=(1-weight)*baseline[eligible]+weight*prior[eligible]
        out.append({"week":int(w),"weight":weight,"n":len(test),"mae_sum":float(np.abs(pred-test.actual_ppr.to_numpy(float)).sum()),"sq_sum":float(np.square(pred-test.actual_ppr.to_numpy(float)).sum()),"eligible":int(eligible.sum())})
if not out:raise RuntimeError("Insufficient earlier-week WR training samples")
o=pd.DataFrame(out)
for weight,g in o.groupby("weight"):
    n=g.n.sum()
    print(f"role_blend={weight:.0%} rows={n} eligible={g.eligible.sum()} MAE={g.mae_sum.sum()/n:.4f} RMSE={(g.sq_sum.sum()/n)**.5:.4f}")
base=o[o.weight==0].mae_sum.sum()
best=o.groupby("weight").mae_sum.sum().idxmin()
print("Best tested weight",best,"(diagnostic, not automatic promotion)")
print("No live AI Score or ranking changes; PPR holdout does not prove AI rank improvement.")
