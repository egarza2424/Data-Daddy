"""Exploratory same-week injury-report WR target walk-forward.

Historical injury report timing is NOT verified; this is NOT a deployable
pregame model. Only past chronological weeks estimate adjustment.
"""
from pathlib import Path
import numpy as np
import pandas as pd
STATS=Path("historical-data/player_stats_2025.csv")
EVENTS=Path("projection-model/validation/2025-pregame-injury-event-candidates.csv")
OUT=Path("projection-model/validation/2025-wr-injury-event-walkforward-summary.csv")
DETAIL=Path("projection-model/validation/2025-wr-injury-event-walkforward-detail.csv")

def main():
    d=pd.read_csv(STATS,low_memory=False)
    e=pd.read_csv(EVENTS,low_memory=False)
    d=d[d.position.eq("WR")].copy()
    for col in ("season","week","targets"):
        d[col]=pd.to_numeric(d[col],errors="coerce")
    d=d.sort_values(["season","player_id","week"])
    d["prior3"]=d.groupby(["season","player_id"]).targets.transform(
        lambda s:s.shift(1).rolling(3,min_periods=2).mean())
    flags=e[["season","week","player_id"]].drop_duplicates().assign(event=True)
    d=d.merge(flags,on=["season","week","player_id"],how="left")
    d["event"]=d.event.fillna(False).astype(bool)
    d=d.dropna(subset=["prior3","targets"]).sort_values(["season","week"]).copy()
    rows=[]
    for (season,week),test in d.groupby(["season","week"],sort=True):
        train=d[(d.season<season)|((d.season==season)&(d.week<week))]
        exposed=train[train.event]
        control=train[~train.event]
        if len(train)<200 or len(exposed)<20 or len(control)<100:
            continue
        exposed_delta=(exposed.targets-exposed.prior3).mean()
        control_delta=(control.targets-control.prior3).mean()
        effect=(exposed_delta-control_delta)*len(exposed)/(len(exposed)+40)
        for r in test.itertuples():
            baseline=max(0,float(r.prior3))
            challenger=max(0,baseline+(effect if r.event else 0))
            rows.append({"season":int(season),"week":int(week),"player_id":r.player_id,
                         "event":bool(r.event),"actual_targets":float(r.targets),
                         "baseline":baseline,"challenger":challenger,
                         "train_event_rows":len(exposed),"learned_adjustment":effect})
    if not rows: raise RuntimeError("Not enough prior event weeks for walk-forward evaluation")
    detail=pd.DataFrame(rows)
    DETAIL.parent.mkdir(parents=True,exist_ok=True)
    detail.to_csv(DETAIL,index=False)
    summaries=[]
    for label,sub in (("all",detail),("injury_event",detail[detail.event]),("other",detail[~detail.event])):
        if sub.empty: continue
        actual=sub.actual_targets
        summaries.append({"group":label,"player_weeks":len(sub),
                          "baseline_mae":round((actual-sub.baseline).abs().mean(),4),
                          "challenger_mae":round((actual-sub.challenger).abs().mean(),4),
                          "baseline_rmse":round(np.sqrt(((actual-sub.baseline)**2).mean()),4),
                          "challenger_rmse":round(np.sqrt(((actual-sub.challenger)**2).mean()),4),
                          "actual_target_increase_rate":round((actual>sub.baseline).mean(),4)})
    pd.DataFrame(summaries).to_csv(OUT,index=False)
    for s in summaries: print(s)
    print("EXPLORATORY ONLY: injury report timing not verified; no live model or ranking changes.")
if __name__=="__main__":main()
