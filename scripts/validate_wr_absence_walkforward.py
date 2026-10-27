"""Review-only walk-forward WR target forecast test.

The current-week teammate absence flag is NOT known pregame, so it must
never be used as a feature. Test whether LAST week's observed absence
proxy predicts the next appearance. Compare a fixed prior-3 target
baseline against a train-only fitted lagged-absence adjustment.
Chronological season/week folds; no same-week outcome leakage.
"""
from pathlib import Path
import numpy as np
import pandas as pd

SRC=Path("projection-model/validation/historical-injury-opportunity-foundation.csv")
OUT=Path("projection-model/validation/wr-lagged-absence-walkforward-summary.csv")
DETAIL=Path("projection-model/validation/wr-lagged-absence-walkforward-detail.csv")

def main():
    df=pd.read_csv(SRC,low_memory=False)
    df=df[df.position.eq("WR")].copy()
    for c in ("season","week","prior_targets_3game","target_week_targets_outcome"):
        df[c]=pd.to_numeric(df[c],errors="coerce")
    df["absence"]=df.top_teammate_absent_proxy.fillna(False).astype(str).str.lower().eq("true")
    df=df.sort_values(["player_id","season","week"])
    grp=df.groupby(["season","player_id"],sort=False)
    df["lagged_absence"]=grp.absence.shift(1)
    df["prior_week"]=grp.week.shift(1)
    # Only immediate consecutive weeks: prevent stale events after bye/missed games.
    df=df[df.week.sub(df.prior_week).eq(1)].copy()
    df=df.dropna(subset=["prior_targets_3game","target_week_targets_outcome","lagged_absence"])
    df["lagged_absence"]=df.lagged_absence.astype(bool)
    df=df.sort_values(["season","week"])
    results=[]
    # Prior weeks only; require enough positive and negative training cases.
    for (season,week),test in df.groupby(["season","week"],sort=True):
        train=df[(df.season<season)|((df.season==season)&(df.week<week))]
        positive=train[train.lagged_absence]
        negative=train[~train.lagged_absence]
        if len(train)<150 or len(positive)<12 or len(negative)<50:
            continue
        residual=train.target_week_targets_outcome-train.prior_targets_3game
        # Shrunk adjustment estimated exclusively from earlier weeks.
        pos_res=(positive.target_week_targets_outcome-positive.prior_targets_3game).mean()
        neg_res=(negative.target_week_targets_outcome-negative.prior_targets_3game).mean()
        effect=(pos_res-neg_res)*len(positive)/(len(positive)+40)
        for _,r in test.iterrows():
            baseline=max(0,float(r.prior_targets_3game))
            challenger=max(0,baseline+(effect if r.lagged_absence else 0))
            actual=float(r.target_week_targets_outcome)
            results.append({"season":int(season),"week":int(week),"player_id":r.player_id,
                            "lagged_absence":bool(r.lagged_absence),
                            "actual_targets":actual,"baseline_targets":baseline,
                            "challenger_targets":challenger,"training_absence_rows":len(positive),
                            "train_only_absence_adjustment":effect})
    if not results:
        raise RuntimeError("Insufficient walk-forward folds; no claims can be made")
    out=pd.DataFrame(results)
    OUT.parent.mkdir(parents=True,exist_ok=True)
    out.to_csv(DETAIL,index=False)
    summary=[]
    for label,part in [("all",out),("lagged_absence",out[out.lagged_absence]),("no_lagged_absence",out[~out.lagged_absence])]:
        summary.append({"group":label,"rows":len(part),"baseline_mae":round(np.mean(abs(part.actual_targets-part.baseline_targets)),4),
                        "challenger_mae":round(np.mean(abs(part.actual_targets-part.challenger_targets)),4),
                        "baseline_rmse":round(np.sqrt(np.mean((part.actual_targets-part.baseline_targets)**2)),4),
                        "challenger_rmse":round(np.sqrt(np.mean((part.actual_targets-part.challenger_targets)**2)),4)})
    pd.DataFrame(summary).to_csv(OUT,index=False)
    for row in summary: print(row)
    print("Review only. Tests targets, NOT PPR or injury verification. No live model changes.")
if __name__=="__main__":
    main()
