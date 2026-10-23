"""Research-only historical RB workload-retention backtest.

A missing weekly stat row is only an absence proxy, NOT verified injury.
Compare the first proxy-absence week's carry gain with the next consecutive
proxy-absence week, using only earlier games for the baseline. No model writes.
"""
import argparse
from pathlib import Path
import pandas as pd


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--stats", required=True)
    p.add_argument("--season", type=int, default=2025)
    p.add_argument("--output", default="projection-model/validation/2025-rb-absence-retention-backtest.csv")
    args = p.parse_args()
    df = pd.read_csv(args.stats, low_memory=False)
    team_col = next((c for c in ("recent_team", "team") if c in df), None)
    rush_col = next((c for c in ("carries", "rushing_attempts") if c in df), None)
    if not team_col or not rush_col or not {"season", "week", "position", "player_id"}.issubset(df):
        raise ValueError("Missing required weekly player-stat columns")
    df = df.loc[(df.season == args.season) & df.position.eq("RB")].copy()
    df["carries"] = pd.to_numeric(df[rush_col], errors="coerce").fillna(0)
    df["week"] = pd.to_numeric(df.week, errors="coerce").astype(int)
    df["player_id"] = df.player_id.astype(str)
    rows = []
    for team, team_df in df.groupby(team_col):
        by_week = {w: frame.set_index("player_id") for w, frame in team_df.groupby("week")}
        last_starter_absence_week = {}
        for week in range(5, 17):
            previous = team_df.loc[(team_df.week >= week - 4) & (team_df.week < week)]
            if previous.empty or week not in by_week or week + 1 not in by_week:
                continue
            # Proxy lead RB must have at least 3 of 4 prior appearances
            # and >= 10 average carries in those appearances.
            leaders = previous.groupby("player_id").carries.agg(["mean", "count"])
            leaders = leaders.loc[(leaders["count"] >= 3) & (leaders["mean"] >= 10)]
            if leaders.empty:
                continue
            starter = leaders["mean"].idxmax()
            if starter in by_week[week].index or starter in by_week[week + 1].index:
                continue
            # One non-overlapping observation per starter absence episode:
            # consecutive missing weeks must not become new event starts.
            if last_starter_absence_week.get(starter) == week - 1:
                last_starter_absence_week[starter] = week
                continue
            last_starter_absence_week[starter] = week
            for beneficiary in set(by_week[week].index) & set(by_week[week + 1].index):
                if beneficiary == starter:
                    continue
                earlier = previous.loc[previous.player_id.eq(beneficiary), "carries"]
                if len(earlier) < 2:
                    continue
                baseline = float(earlier.mean())
                first = float(by_week[week].loc[beneficiary, "carries"])
                second = float(by_week[week + 1].loc[beneficiary, "carries"])
                gain = first - baseline
                if gain < 3:
                    continue
                retained = (second - baseline) / gain
                rows.append({
                    "season": args.season, "team": team, "first_absence_week": week,
                    "proxy_starter_id": starter, "beneficiary_id": beneficiary,
                    "baseline_games": len(earlier), "baseline_carries": round(baseline, 2),
                    "first_absence_carries": first, "next_absence_carries": second,
                    "first_carry_gain": round(gain, 2),
                    "observed_retention_ratio": round(retained, 3),
                    "error_25pct_carries": round(abs(second - (baseline + 0.25 * gain)), 2),
                    "error_50pct_carries": round(abs(second - (baseline + 0.50 * gain)), 2),
                    "evidence_type": "UNVERIFIED_ABSENCE_PROXY",
                })
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    columns = ["season", "team", "first_absence_week", "proxy_starter_id", "beneficiary_id",
               "baseline_games", "baseline_carries", "first_absence_carries",
               "next_absence_carries", "first_carry_gain", "observed_retention_ratio",
               "error_25pct_carries", "error_50pct_carries", "evidence_type"]
    result = pd.DataFrame(rows, columns=columns)
    result.to_csv(out, index=False)
    print(f"Saved {len(result)} proxy-absence player cases to {out}")
    if len(result):
        print("Mean absolute carry error:", result[["error_25pct_carries", "error_50pct_carries"]].mean().round(3).to_dict())
    else:
        print("No qualifying cases; no retention conclusion.")


if __name__ == "__main__":
    main()
