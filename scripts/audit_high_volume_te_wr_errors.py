"""Read-only pregame target-volume calibration audit for TE and WR."""
import pandas as pd

stats = pd.read_csv("historical-data/player_stats_2025.csv", low_memory=False)
pred = pd.read_csv("projection-model/2025-ppr-walkforward-predictions.csv", low_memory=False)
pred = pred.loc[pred.model.eq("F_position_specific") & pred.position.isin(["TE", "WR"])].copy()
for frame in (stats, pred):
    frame["player_id"] = frame.player_id.astype(str)
    frame["week"] = pd.to_numeric(frame.week)
    frame["season"] = pd.to_numeric(frame.season)
stats["targets"] = pd.to_numeric(stats.targets, errors="coerce").fillna(0)
stats = stats.loc[stats.position.isin(["TE", "WR"])].copy()
histories = {(s, p, t): g.sort_values("week") for (s, p, t), g in stats.groupby(["season", "player_id", "team"])}

records = []
for row in pred.itertuples(index=False):
    h = histories.get((row.season, row.player_id, row.team))
    prior = h.loc[h.week.lt(row.week)].tail(3) if h is not None else None
    if prior is None or len(prior) < 3:
        continue
    records.append({
        "position": row.position, "week": row.week, "player_id": row.player_id,
        "average_targets": float(prior.targets.mean()),
        "minimum_targets": float(prior.targets.min()),
        "actual_ppr": float(row.actual_ppr),
        "projected_ppr": float(row.projected_ppr),
    })
df = pd.DataFrame(records)
if df.empty:
    raise RuntimeError("No matched pregame histories")
df["signed_error"] = df.projected_ppr - df.actual_ppr
df["absolute_error"] = df.signed_error.abs()
df["volume_band"] = pd.cut(df.average_targets, [-0.01, 2, 4, 6, 8, float("inf")],
                           labels=["0-2", "2-4", "4-6", "6-8", "8+"])
df["sustained_band"] = pd.cut(df.minimum_targets, [-0.01, 1, 3, 5, 8, float("inf")],
                              labels=["0-1", "2-3", "4-5", "6-8", "9+"])
print("Matched historical player-weeks with three prior same-team appearances:", len(df))
print("Signed error = projected PPR minus actual PPR; positive means overprojection.")
for label, frame in [("ALL", df), *list(df.groupby("position"))]:
    print(f"{label}: n={len(frame)} bias={frame.signed_error.mean():+.4f} MAE={frame.absolute_error.mean():.4f}")
for band_column in ("volume_band", "sustained_band"):
    print("\\n", band_column)
    for (position, band), group in df.groupby(["position", band_column], observed=True):
        print(f"{position} {band}: n={len(group)} avg_targets={group.average_targets.mean():.2f} "
              f"actual={group.actual_ppr.mean():.3f} projected={group.projected_ppr.mean():.3f} "
              f"bias={group.signed_error.mean():+.3f} MAE={group.absolute_error.mean():.3f} "
              f"overprojection_rate={(group.signed_error > 0).mean():.1%}")
print("Descriptive audit only; no model or live changes.")
