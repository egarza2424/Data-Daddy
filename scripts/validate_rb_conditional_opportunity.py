"""Research-only conditional RB trend gate on frozen pregame predictions.

Threshold selection uses 2023-24 only; 2025 is an untouched evaluation season.
This experiment cannot assess limited-history rookies because the upstream
trend backtest requires four prior games. No production files are modified.
"""
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

OUT=Path("projection-model/validation")
YEARS=(2023,2024,2025)
THRESHOLDS=(0.0,1.0,2.0,3.0,4.0,6.0)
SHRINKAGES=(0.25,0.5,0.75,1.0)

def load(year):
    p=OUT/f"{year}-rb-opportunity-trends-backtest.csv"
    if not p.exists():
        raise FileNotFoundError(f"Missing {p}. Run the upstream opportunity-trends workflow and add its artifacts.")
    d=pd.read_csv(p)
    cols=["week","player_id","actual_ppr","opportunity_trend","baseline_prediction","opportunity_prediction","prior_games"]
    d=d.dropna(subset=cols).copy()
    d["season"]=year
    return d

def predict(d,threshold,shrinkage):
    active=d.opportunity_trend.to_numpy(float)>threshold
    base=d.baseline_prediction.to_numpy(float)
    alt=d.opportunity_prediction.to_numpy(float)
    return base+np.where(active,shrinkage*(alt-base),0),active

def score(d,p):
    y=d.actual_ppr.to_numpy(float)
    rho=spearmanr(y,p).statistic if len(y)>2 else np.nan
    return {"MAE":float(np.mean(np.abs(y-p))),"RMSE":float(np.sqrt(np.mean((y-p)**2))),
            "Spearman":float(rho) if np.isfinite(rho) else np.nan,"rows":len(y)}

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    frames={y:load(y) for y in YEARS}
    training=pd.concat([frames[2023],frames[2024]],ignore_index=True)
    selection=[]
    for threshold in THRESHOLDS:
        for shrinkage in SHRINKAGES:
            p,active=predict(training,threshold,shrinkage)
            selection.append({"threshold":threshold,"shrinkage":shrinkage,
                              "activated":int(active.sum()),**score(training,p)})
    search=pd.DataFrame(selection).sort_values(["MAE","threshold","shrinkage"])
    search.to_csv(OUT/"rb-conditional-opportunity-threshold-search.csv",index=False)
    best=search.iloc[0]
    threshold=float(best.threshold)
    shrinkage=float(best.shrinkage)
    results=[]
    detail=[]
    for year,d in frames.items():
        challenger,active=predict(d,threshold,shrinkage)
        baseline=d.baseline_prediction.to_numpy(float)
        for label,subset in [("all",np.ones(len(d),dtype=bool)),
                             ("activated",active),("not_activated",~active)]:
            if not subset.any():
                continue
            for model,p in [("Model F baseline",baseline),("Conditional opportunity",challenger)]:
                results.append({"season":year,"group":label,"model":model,
                                "threshold":threshold,"shrinkage":shrinkage,
                                "activated":int(active.sum()),**score(d.loc[subset],p[subset])})
        x=d.copy()
        x["conditional_prediction"]=challenger
        x["adjustment_active"]=active
        detail.append(x)
    pd.DataFrame(results).to_csv(OUT/"rb-conditional-opportunity-summary.csv",index=False)
    pd.concat(detail,ignore_index=True).to_csv(OUT/"rb-conditional-opportunity-backtest.csv",index=False)
    print(f"Selected on 2023-24 only: trend > {threshold} opportunities; shrinkage {shrinkage}")
    print(pd.DataFrame(results).to_string(index=False))
    print("LIMITATION: four-prior-game eligibility; no short-history rookie conclusions.")
    print("Research only; production Model F unchanged.")

if __name__=="__main__":
    main()
