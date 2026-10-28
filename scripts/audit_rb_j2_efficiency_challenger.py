"""Read-only RB J2 efficiency challenger: tune on 2024, hold out 2025.

Apply a small flat PPR deduction ONLY to pregame high-volume/low-efficiency
RBs (>=12 recent carries/game and <4.0 recent rushing YPC).
No production projections or weights are changed.
"""
from pathlib import Path
import pandas as pd

ROOT = Path("projection-model")
VAL = ROOT / "validation"
CANDIDATES = (0.0, 0.25, 0.5, 0.75, 1.0, 1.5)


def load(season):
    history = pd.read_csv(ROOT / f"{season}-historical-ppr-dataset.csv")
    pred = pd.read_csv(VAL / f"{season}-rb-model-j2-predictions.csv")
    pred = pred.loc[pred.model.eq("J2_RB_role_stability")].copy()
    hist = history.loc[history.position.eq("RB"), [
        "season", "week", "player_id", "rb_carries_pg",
        "rb_rush_yards_pg",
    ]]
    d = pred.merge(hist, on=["season", "week", "player_id"],
                   how="left", validate="one_to_one")
    if d.empty or d[["projected_ppr", "actual_ppr", "rb_carries_pg",
                      "rb_rush_yards_pg"]].isna().any().any():
        raise ValueError(f"Missing or invalid {season} historical rows")
    ypc = d.rb_rush_yards_pg.div(d.rb_carries_pg.where(d.rb_carries_pg.gt(0)))
    d["low_eff_volume"] = d.rb_carries_pg.ge(12) & ypc.lt(4.0)
    d["season_audit"] = season
    return d


def measure(d, deduction):
    x = d.copy()
    x["challenger_ppr"] = (
        x.projected_ppr - deduction * x.low_eff_volume.astype(float)
    ).clip(lower=0)
    x["abs_error"] = (x.challenger_ppr - x.actual_ppr).abs()
    x["signed_error"] = x.challenger_ppr - x.actual_ppr
    rows = []
    for label, group in [
        ("all_RBs", x),
        ("high_volume_low_efficiency", x.loc[x.low_eff_volume]),
        ("other_RBs", x.loc[~x.low_eff_volume]),
    ]:
        rows.append(dict(group=label, n=len(group),
                         mae=group.abs_error.mean(),
                         bias=group.signed_error.mean()))
    # Recall among actual top-24 RBs within each historical week.
    hits = actual_top = 0
    for _, week in x.groupby(["season_audit", "week"]):
        actual_ids = set(week.nlargest(24, "actual_ppr").player_id)
        projected_ids = set(week.nlargest(24, "challenger_ppr").player_id)
        hits += len(actual_ids & projected_ids)
        actual_top += len(actual_ids)
    recall = hits / actual_top if actual_top else float("nan")
    for row in rows:
        row["top24_recall"] = recall if row["group"] == "all_RBs" else float("nan")
        row["deduction"] = deduction
    return rows


def main():
    train, heldout = load(2024), load(2025)
    results = []
    for name, frame in [("2024_selection", train), ("2025_holdout", heldout)]:
        for amount in CANDIDATES:
            for row in measure(frame, amount):
                results.append(dict(period=name, **row))
    report = pd.DataFrame(results)
    # Select ONLY on 2024 all-RB MAE; no 2025 tuning.
    selection = report.loc[(report.period == "2024_selection") &
                           (report.group == "all_RBs")]
    best = selection.sort_values(["mae", "deduction"]).iloc[0]
    selected = float(best.deduction)
    print("2024 selected deduction:", selected)
    for period in ("2024_selection", "2025_holdout"):
        print("\n", period, "all RBs and affected subgroup:")
        print(report.loc[(report.period == period) &
                         (report.deduction.isin([0.0, selected])) &
                         (report.group.isin(["all_RBs", "high_volume_low_efficiency"]))].
              round(4).to_string(index=False))
    out = VAL / "rb-j2-efficiency-challenger-2024-selection-2025-holdout.csv"
    report.to_csv(out, index=False)
    print("Saved", out)
    # Independent 2025 weekly and player-level diagnostic; selected amount fixed by 2024.
    detail = heldout.copy()
    detail["challenger_ppr"] = (detail.projected_ppr - selected * detail.low_eff_volume.astype(float)).clip(lower=0)
    detail["baseline_abs_error"] = (detail.projected_ppr - detail.actual_ppr).abs()
    detail["challenger_abs_error"] = (detail.challenger_ppr - detail.actual_ppr).abs()
    detail["mae_improvement"] = detail.baseline_abs_error - detail.challenger_abs_error
    weekly = []
    for week_number, frame in detail.groupby("week"):
        actual_top = set(frame.nlargest(24, "actual_ppr").player_id)
        baseline_top = set(frame.nlargest(24, "projected_ppr").player_id)
        challenger_top = set(frame.nlargest(24, "challenger_ppr").player_id)
        affected = frame.loc[frame.low_eff_volume]
        weekly.append(dict(week=int(week_number), rb_count=len(frame),
            affected_count=len(affected), baseline_mae=frame.baseline_abs_error.mean(),
            challenger_mae=frame.challenger_abs_error.mean(),
            mae_improvement=frame.mae_improvement.mean(),
            affected_mae_improvement=affected.mae_improvement.mean(),
            baseline_top24_recall=len(actual_top & baseline_top)/len(actual_top),
            challenger_top24_recall=len(actual_top & challenger_top)/len(actual_top)))
    weekly = pd.DataFrame(weekly).sort_values("week")
    weekly_path = VAL / "2025-rb-j2-efficiency-challenger-weekly.csv"
    weekly.to_csv(weekly_path, index=False)
    print("\\n2025 HELD-OUT WEEKLY RESULTS (positive MAE improvement is better):")
    print(weekly.round(4).to_string(index=False))
    affected = detail.loc[detail.low_eff_volume].copy()
    affected_path = VAL / "2025-rb-j2-efficiency-challenger-player-impact.csv"
    affected.sort_values("mae_improvement").to_csv(affected_path, index=False)
    cols = ["week", "player_name", "projected_ppr", "challenger_ppr", "actual_ppr", "mae_improvement"]
    print("\\nBIGGEST REGRESSIONS (affected players):")
    print(affected.nsmallest(10, "mae_improvement")[cols].round(3).to_string(index=False))
    print("\\nBIGGEST IMPROVEMENTS (affected players):")
    print(affected.nlargest(10, "mae_improvement")[cols].round(3).to_string(index=False))
    print("Saved", weekly_path, "and", affected_path)
    print("READ ONLY: no live model, rankings or projections changed.")


if __name__ == "__main__":
    main()
