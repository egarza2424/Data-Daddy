"""Audit historical waiver eligibility without inventing historical ownership."""
from pathlib import Path
import pandas as pd

OUT=Path("projection-model/validation")
def main():
    ranked=pd.read_csv(OUT/"rb-breakout-ranked-player-weeks.csv")
    keys=["season","week","player_id"]
    for c in keys:
        if c not in ranked: raise ValueError(f"Missing {c}")
    ownership=Path("historical-data/rb_weekly_ownership_2023_2025.csv")
    report=[]
    if not ownership.exists():
        for (year,week),g in ranked.groupby(["season","week"]):
            report.append(dict(season=year,week=week,candidates=len(g),verified_eligible=0,
                               ownership_verified=0,status="HISTORICAL_OWNERSHIP_UNAVAILABLE"))
        pd.DataFrame(report).to_csv(OUT/"rb-waiver-eligibility-audit.csv",index=False)
        print("Historical ownership missing. Waiver precision is NOT calculated; no present-day ownership backfill.")
        return
    o=pd.read_csv(ownership)
    required=set(keys+["ownership_pct","source","observed_at"])
    if missing:=required-set(o.columns): raise ValueError(f"Ownership file missing {sorted(missing)}")
    if o.duplicated(keys+["source"]).any(): raise ValueError("Duplicate platform/player/week ownership")
    o["ownership_pct"]=pd.to_numeric(o.ownership_pct,errors="coerce")
    o["observed_at"]=pd.to_datetime(o.observed_at,utc=True,errors="coerce")
    # No kickoff timestamps in current ranking data; refuse unverifiable temporal joins.
    if "kickoff_utc" not in ranked:
        raise ValueError("Historical ownership supplied, but ranked player-weeks lack kickoff_utc. Cannot prove pregame eligibility.")
    ranked["kickoff_utc"]=pd.to_datetime(ranked.kickoff_utc,utc=True,errors="coerce")
    x=ranked.merge(o,on=keys,how="left",validate="one_to_many")
    if (x.observed_at>=x.kickoff_utc).any():
        raise ValueError("Post-kickoff ownership detected; exclude or correct source records")
    print("Pregame ownership joined; eligibility analysis requires verified source coverage policy.")
    raise RuntimeError("Review platform coverage and historical ownership source before publishing waiver precision.")
if __name__=="__main__": main()
