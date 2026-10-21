"""Non-publishing Week 7 TE PPG challenger. No live projection edits."""
import argparse
import json
from pathlib import Path
import pandas as pd

def build_challenger(projections, stats, target_week, weight=0.5):
    if not 0 <= weight <= 1:
        raise ValueError("Weight must be between 0 and 1")
    te = projections.loc[projections["position"].eq("TE")].copy()
    if te.empty:
        raise ValueError("No TE projections found")
    rows = pd.DataFrame(stats["players"])
    required = {"season", "week", "position", "team", "player_display_name"}
    if not required.issubset(rows.columns):
        raise ValueError(f"Missing weekly stat fields: {sorted(required-set(rows.columns))}")
    rows = rows.loc[
        rows["position"].eq("TE")
        & pd.to_numeric(rows["season"], errors="coerce").eq(2026)
        & pd.to_numeric(rows["week"], errors="coerce").lt(target_week)
    ].copy()
    for col in ["receptions", "receiving_yards", "receiving_tds",
                "rushing_yards", "rushing_tds"]:
        rows[col] = pd.to_numeric(rows.get(col, 0), errors="coerce").fillna(0)
    rows["ppr"] = (rows["receptions"] + rows["receiving_yards"]/10
                   + 6*rows["receiving_tds"] + rows["rushing_yards"]/10
                   + 6*rows["rushing_tds"])
    def normalize(name):
        import re
        name = re.sub(r"\s+(jr\.?|sr\.?|ii|iii|iv)$", "", str(name).lower().strip())
        return re.sub(r"[^a-z0-9]", "", name)
    rows["key"] = rows["player_display_name"].map(normalize) + "|" + rows["team"].astype(str).str.upper()
    te["key"] = te["player_name"].map(normalize) + "|" + te["team"].astype(str).str.upper()
    grouped = rows.groupby("key")["ppr"].agg(["count", "mean"])
    te["prior_games"] = te["key"].map(grouped["count"]).fillna(0).astype(int)
    te["season_ppg"] = te["key"].map(grouped["mean"])
    te["challenger_ppr"] = te["projected_ppr"].astype(float)
    eligible = te["prior_games"].ge(2) & te["season_ppg"].notna()
    te.loc[eligible, "challenger_ppr"] = (
        (1-weight)*te.loc[eligible, "projected_ppr"].astype(float)
        + weight*te.loc[eligible, "season_ppg"]
    )
    te["challenger_ppr"] = te["challenger_ppr"].round(2)
    te["challenger_rank"] = te["challenger_ppr"].rank(method="min", ascending=False).astype(int)
    return te.drop(columns=["key"]).sort_values(["challenger_rank", "player_name"])

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--week", type=int, default=7)
    parser.add_argument("--weight", type=float, default=0.5)
    args = parser.parse_args()
    projections = pd.read_csv(f"projection-model/2026-week{args.week}-ppr-projections.csv")
    stats = json.loads(Path("nfl-stats.json").read_text(encoding="utf-8"))
    challenger = build_challenger(projections, stats, args.week, args.weight)
    output = Path(f"projection-model/validation/2026-week{args.week}-te-ppg-challenger.csv")
    output.parent.mkdir(parents=True, exist_ok=True)
    challenger.to_csv(output, index=False)
    print(f"Saved {len(challenger)} TE challenger rows to {output}")
    print(challenger.loc[challenger["player_name"].isin(
        ["Juwan Johnson", "Travis Kelce", "Jake Ferguson"]
    ), ["player_name", "prior_games", "season_ppg", "projected_ppr", "challenger_ppr", "challenger_rank"]].to_string(index=False))
    print("CHALLENGER ONLY: live projections unchanged")

if __name__ == "__main__":
    main()
