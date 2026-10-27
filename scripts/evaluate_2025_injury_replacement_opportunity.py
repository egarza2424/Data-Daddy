"""Review-only injury-event target changes, using strictly earlier appearances.

Descriptive, not causal/predictive. Event duplicates are de-duplicated at
candidate-player-week level; event counts reported separately.
"""
from pathlib import Path
import pandas as pd

STATS=Path("historical-data/player_stats_2025.csv")
EVENTS=Path("projection-model/validation/2025-pregame-injury-event-candidates.csv")
OUT=Path("projection-model/validation/2025-injury-replacement-opportunity-summary.csv")
DETAIL=Path("projection-model/validation/2025-injury-replacement-opportunity-detail.csv")

def main():
    stats=pd.read_csv(STATS,low_memory=False)
    events=pd.read_csv(EVENTS,low_memory=False)
    stats=stats[stats.position.isin(["WR","TE"])].copy()
    for c in ["season","week","targets"]:
        stats[c]=pd.to_numeric(stats[c],errors="coerce")
    stats=stats.sort_values(["season","player_id","week"])
    stats["prior3_targets"]=stats.groupby(["season","player_id"]).targets.transform(
        lambda x:x.shift(1).rolling(3,min_periods=2).mean())
    # Player-week may appear multiple times when more than one teammate has a report.
    event_keys=events[["season","week","player_id"]].drop_duplicates()
    event_keys["injury_event_candidate"]=True
    stats=stats.merge(event_keys,on=["season","week","player_id"],how="left")
    stats["injury_event_candidate"]=stats.injury_event_candidate.fillna(False).astype(bool)
    valid=stats.dropna(subset=["prior3_targets","targets"]).copy()
    valid["target_change"]=valid.targets-valid.prior3_targets
    valid["targets_increased"]=valid.target_change.gt(0)
    valid[["season","week","player_id","player_name","position","team","targets",
           "prior3_targets","target_change","injury_event_candidate"]].to_csv(DETAIL,index=False)
    rows=[]
    for pos in ["WR","TE"]:
        for flag in [True,False]:
            group=valid[(valid.position==pos)&(valid.injury_event_candidate==flag)]
            rows.append({"position":pos,"injury_event_candidate":flag,"player_weeks":len(group),
                         "distinct_players":group.player_id.nunique(),
                         "mean_prior3_targets":round(group.prior3_targets.mean(),3),
                         "mean_current_targets":round(group.targets.mean(),3),
                         "mean_target_change":round(group.target_change.mean(),3),
                         "target_increase_rate":round(group.targets_increased.mean(),4)})
    OUT.parent.mkdir(parents=True,exist_ok=True)
    pd.DataFrame(rows).to_csv(OUT,index=False)
    for row in rows:print(row)
    print(f"Distinct injury-event keys: {events[['season','week','injured_teammate_id']].drop_duplicates().shape[0]}")
    print("DESCRIPTIVE ONLY: report timing unverified; matched candidates are not confirmed replacements.")
    print("No model or live changes.")
if __name__=="__main__":main()
