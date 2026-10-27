"""Review-only historical injury-opportunity dataset foundation.

Uses historical weekly player stats. A teammate's absence is a measured
week-over-week absence proxy, NOT a verified injury, IR, or trade event.
No route participation data is inferred from targets. Features are based
on prior weeks only; actual target-week PPR is an evaluation outcome.
"""
from pathlib import Path
import pandas as pd

OUT = Path("projection-model/validation/historical-injury-opportunity-foundation.csv")
FILES = [Path(f"historical-data/player_stats_{year}.csv") for year in (2023, 2024, 2025)]
def main():
    available = [p for p in FILES if p.exists()]
    if not available:
        raise SystemExit("No historical weekly player stats found")
    frames = []
    for p in available:
        d = pd.read_csv(p, low_memory=False)
        needed = {"season","week","player_id","player_name","position","team","targets","receptions"}
        missing = needed - set(d.columns)
        if missing:
            raise SystemExit(f"{p}: missing {sorted(missing)}")
        frames.append(d)
    df = pd.concat(frames, ignore_index=True)
    df = df[df.position.isin(["WR","TE"])].copy()
    df["week"] = pd.to_numeric(df.week, errors="coerce")
    df["targets"] = pd.to_numeric(df.targets, errors="coerce").fillna(0)
    df["receptions"] = pd.to_numeric(df.receptions, errors="coerce").fillna(0)
    df = df.dropna(subset=["week","player_id","team"]).sort_values(["season","week"])
    # Candidate teammate: prior week's most-targeted receiver, excluding self.
    previous = df[["season","week","team","player_id","player_name","targets"]].copy()
    previous["week"] += 1
    previous = previous.rename(columns={"player_id":"teammate_id","player_name":"teammate_name","targets":"teammate_previous_targets"})
    previous = previous.sort_values("teammate_previous_targets", ascending=False).drop_duplicates(["season","week","team"])
    current_ids = df[["season","week","team","player_id"]].rename(columns={"player_id":"active_player_id"})
    prev = previous.merge(current_ids, left_on=["season","week","team","teammate_id"],right_on=["season","week","team","active_player_id"],how="left",indicator=True)
    prev["top_teammate_absent_proxy"] = prev["_merge"].eq("left_only")
    prev = prev.drop(columns=["active_player_id","_merge"])
    df = df.merge(prev, on=["season","week","team"],how="left")
    df = df[df.player_id.ne(df.teammate_id)].copy()
    df = df.sort_values(["player_id","season","week"])
    grouped = df.groupby(["player_id","season"], sort=False)
    df["prior_targets_3game"] = grouped.targets.transform(lambda x: x.shift(1).rolling(3,min_periods=1).mean())
    df["prior_receptions_3game"] = grouped.receptions.transform(lambda x: x.shift(1).rolling(3,min_periods=1).mean())
    df["target_week_targets_outcome"] = df.targets
    df["target_week_receptions_outcome"] = df.receptions
    df["route_share_pre"] = pd.NA
    df["route_share_post"] = pd.NA
    df["injury_confirmed"] = pd.NA
    df["event_classification"] = "unverified_teammate_absence_proxy"
    cols = ["season","week","player_id","player_name","position","team","teammate_id","teammate_name","teammate_previous_targets","top_teammate_absent_proxy","prior_targets_3game","prior_receptions_3game","target_week_targets_outcome","target_week_receptions_outcome","route_share_pre","route_share_post","injury_confirmed","event_classification"]
    OUT.parent.mkdir(parents=True,exist_ok=True)
    df[cols].to_csv(OUT,index=False)
    print(f"Historical rows: {len(df)}, absent-proxy rows: {int(df.top_teammate_absent_proxy.fillna(False).sum())}")
    print("Route share and confirmed injury fields deliberately blank; no model or live changes.")
if __name__ == "__main__":
    main()
