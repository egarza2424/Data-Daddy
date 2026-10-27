"""Review-only descriptive validation of historical teammate-absence proxy.

This is not an injury classification, route-share estimate, causal test,
or leakage-safe prediction backtest. Reports baseline differences and
prior-to-outcome changes with sample sizes, separated by WR and TE.
"""
from pathlib import Path
import pandas as pd

SOURCE=Path("projection-model/validation/historical-injury-opportunity-foundation.csv")
OUT=Path("projection-model/validation/historical-injury-opportunity-summary.csv")

def main():
    d=pd.read_csv(SOURCE,low_memory=False)
    for col in ("prior_targets_3game","target_week_targets_outcome",
                "prior_receptions_3game","target_week_receptions_outcome"):
        d[col]=pd.to_numeric(d[col],errors="coerce")
    d=d[d.position.isin(("WR","TE")) & d.prior_targets_3game.notna()].copy()
    d["absence_proxy"]=d.top_teammate_absent_proxy.fillna(False).astype(str).str.lower().eq("true")
    d["target_change"]=d.target_week_targets_outcome-d.prior_targets_3game
    d["reception_change"]=d.target_week_receptions_outcome-d.prior_receptions_3game
    rows=[]
    for position in ("WR","TE"):
        for absence in (True,False):
            subset=d[(d.position==position)&(d.absence_proxy==absence)]
            rows.append({
                "position":position,"top_teammate_absent_proxy":absence,
                "sample_player_weeks":len(subset),
                "distinct_players":subset.player_id.nunique(),
                "mean_prior_targets":round(subset.prior_targets_3game.mean(),3),
                "mean_target_week_targets":round(subset.target_week_targets_outcome.mean(),3),
                "mean_target_change":round(subset.target_change.mean(),3),
                "mean_reception_change":round(subset.reception_change.mean(),3),
                "target_increase_rate":round((subset.target_change>0).mean(),4),
                "limitation":"unverified_absence_proxy_not_injury_or_causal_effect"
            })
    OUT.parent.mkdir(parents=True,exist_ok=True)
    pd.DataFrame(rows).to_csv(OUT,index=False)
    for row in rows: print(row)
    print("DESCRIPTIVE ONLY: potential selection bias; no route-share data; no model changes.")

if __name__=="__main__":
    main()
