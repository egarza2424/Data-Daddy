"""Build observed team offensive personnel trends from nflverse participation data.

Usage: python scripts/build_team_personnel_trends.py --input historical-data/pbp_participation_2025.parquet --season 2025 --output data/team_personnel_trends_2025.json
Requires pandas and pyarrow for parquet. Does not invent 2026 observations.
"""
import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

import pandas as pd

PERSONNEL = {"11", "12", "13", "21", "22"}

def package(value):
    """Parse '1 RB, 2 TE, 2 WR' or '1 RB, 2 TE, 2 WR, 0 FB'."""
    if not isinstance(value, str):
        return None
    counts = {}
    for count, position in re.findall(r"(\d+)\s*(RB|TE|WR|FB)", value.upper()):
        counts[position] = counts.get(position, 0) + int(count)
    if not counts:
        return None
    backs = counts.get("RB", 0) + counts.get("FB", 0)
    tight_ends = counts.get("TE", 0)
    return str(backs) + str(tight_ends)

def build(df, season):
    required = {"nflverse_game_id", "play_id", "possession_team", "offense_personnel"}
    if not required.issubset(df.columns):
        raise ValueError("Missing participation columns: " + str(sorted(required-set(df.columns))))
    df = df.dropna(subset=["nflverse_game_id", "play_id", "possession_team"])
    df = df.drop_duplicates(["nflverse_game_id", "play_id", "possession_team"])
    df = df.loc[df["nflverse_game_id"].astype(str).str.startswith(str(season)+"_")].copy()
    df["package"] = df["offense_personnel"].map(package)
    # Never treat missing/unrecognized personnel as 11 personnel.
    result = []
    for team, group in df.groupby("possession_team"):
        known = group.loc[group["package"].notna()]
        total = len(known)
        counts = known["package"].value_counts().to_dict()
        result.append({
            "team": str(team), "season": season, "plays_with_known_personnel": total,
            "plays_missing_personnel": int(len(group)-total),
            "personnel_share_pct": {p: round(100*counts.get(p,0)/total,1) if total else None for p in sorted(PERSONNEL)},
            "two_plus_te_share_pct": round(100*sum(n for p,n in counts.items() if len(p)==2 and p[1].isdigit() and int(p[1])>=2)/total,1) if total else None
        })
    return {"season":season,"source":"nflverse pbp_participation","measurement":"observed offensive personnel per play","teams":sorted(result,key=lambda r:r["team"])}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--input",required=True)
    ap.add_argument("--season",type=int,required=True)
    ap.add_argument("--output",required=True)
    args=ap.parse_args()
    path=Path(args.input)
    if not path.exists():
        raise FileNotFoundError(path)
    df=pd.read_parquet(path) if path.suffix==".parquet" else pd.read_csv(path)
    data=build(df,args.season)
    output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(data,indent=2)+"\n",encoding="utf-8")
    print("Saved personnel observations for",len(data["teams"]),"teams:",output)

if __name__=="__main__":
    main()
