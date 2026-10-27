"""Review-only historical pregame injury-event candidate dataset.

Joins nflverse weekly injury report_status to historical weekly stats.
OUT/DOUBTFUL are report evidence, NOT timestamp-verified pre-kickoff status.
No causal replacement inference and no model/projection/rank changes.
"""
import csv
import io
import urllib.request
from pathlib import Path
import pandas as pd

STATS=Path("historical-data/player_stats_2025.csv")
OUT=Path("projection-model/validation/2025-pregame-injury-event-candidates.csv")
URL="https://github.com/nflverse/nflverse-data/releases/download/injuries/injuries_2025.csv"

def main():
    stats=pd.read_csv(STATS,low_memory=False)
    required={"season","week","player_id","player_name","team","position","targets"}
    if not required.issubset(stats.columns):
        raise RuntimeError(f"Missing stats columns: {sorted(required-set(stats.columns))}")
    with urllib.request.urlopen(urllib.request.Request(URL,headers={"User-Agent":"Mozilla/5.0"}),timeout=90) as response:
        injuries=pd.read_csv(io.BytesIO(response.read()),low_memory=False)
    required_injury={"season","week","gsis_id","team","report_status"}
    if not required_injury.issubset(injuries.columns):
        raise RuntimeError(f"Missing injury columns: {sorted(required_injury-set(injuries.columns))}")
    injuries=injuries[injuries.report_status.astype(str).str.upper().isin(["OUT","DOUBTFUL"])].copy()
    injuries["season"]=pd.to_numeric(injuries.season,errors="coerce")
    injuries["week"]=pd.to_numeric(injuries.week,errors="coerce")
    injuries=injuries.dropna(subset=["gsis_id","team","season","week"])
    # Reject conflicting statuses/duplicate player-week reports rather than guessing.
    injuries=injuries[~injuries.duplicated(["season","week","gsis_id"],keep=False)].copy()
    stats=stats[stats.position.isin(["WR","TE"])].copy()
    stats["week"]=pd.to_numeric(stats.week,errors="coerce")
    stats["season"]=pd.to_numeric(stats.season,errors="coerce")
    stats["targets"]=pd.to_numeric(stats.targets,errors="coerce").fillna(0)
    stats=stats.sort_values(["season","week"])
    prior=stats[["season","week","team","player_id","player_name","position","targets"]].copy()
    prior["week"]=prior["week"]+1
    prior=prior.rename(columns={"player_id":"injured_teammate_id","player_name":"injured_teammate_name","position":"injured_teammate_position","targets":"injured_teammate_prior_targets"})
    reports=injuries[["season","week","team","gsis_id","report_status"]].rename(columns={"gsis_id":"injured_teammate_id","report_status":"injury_report_status"})
    events=reports.merge(prior,on=["season","week","team","injured_teammate_id"],how="inner")
    events=events[events.injured_teammate_prior_targets>=3].copy()
    candidates=stats.merge(events,on=["season","week","team"],how="inner")
    candidates=candidates[candidates.player_id.ne(candidates.injured_teammate_id)].copy()
    candidates=candidates.sort_values(["season","week","player_id"])
    candidates["event_source"]=URL
    candidates["report_timestamp_verified"]=False
    candidates["event_validation_status"]="injury_report_status_only_not_timestamp_verified"
    candidates["route_share_available"]=False
    candidates["pregame_replacement_role_verified"]=False
    columns=["season","week","player_id","player_name","team","position","targets",
             "injured_teammate_id","injured_teammate_name","injured_teammate_position",
             "injured_teammate_prior_targets","injury_report_status",
             "event_source","report_timestamp_verified","event_validation_status",
             "route_share_available","pregame_replacement_role_verified"]
    OUT.parent.mkdir(parents=True,exist_ok=True)
    candidates[columns].to_csv(OUT,index=False)
    print(f"2025 injury report rows (OUT/DOUBTFUL, uniquely matched): {len(injuries)}")
    print(f"Historical teammate injury event matches: {len(events)}")
    print(f"Candidate receiver player-weeks: {len(candidates)}")
    print("Review-only; report timing unverified. No predictive lift or official pregame confirmation claimed.")
if __name__=="__main__":
    main()
