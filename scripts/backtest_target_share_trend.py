"""Read-only TE/WR historical target-share trend experiment."""
import importlib.util
import pandas as pd

spec = importlib.util.spec_from_file_location("model", "scripts/build_ppr_projection_model.py")
model = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model)

data = pd.read_csv("projection-model/2025-historical-ppr-dataset.csv")
stats = pd.read_csv("historical-data/player_stats_2025.csv", low_memory=False)
stats["player_id"] = stats.player_id.astype(str)
data["player_id"] = data.player_id.astype(str)
for col in ("season", "week", "targets"):
    stats[col] = pd.to_numeric(stats[col], errors="coerce").fillna(0)

team_totals = stats.groupby(["season", "week", "team"]).targets.sum().rename("team_targets")
stats = stats.loc[stats.position.isin(["TE", "WR"])].copy()
stats = stats.join(team_totals, on=["season", "week", "team"])
stats["share"] = stats.targets / stats.team_targets.clip(lower=1)
histories = {(season, player, team): group.sort_values("week") for (season, player, team), group in stats.groupby(["season", "player_id", "team"])}

trends = []
history_counts = []
for row in data.itertuples():
    history = histories.get((row.season, row.player_id, row.team))
    if row.position not in ("TE", "WR") or history is None:
        trends.append(0.0)
        history_counts.append(0)
        continue
    prior = history.loc[history.week < row.week].tail(3)
    if len(prior) < 3:
        trends.append(0.0)
        history_counts.append(len(prior))
        continue
    a, b, c = prior.share.tolist()
    trends.append(100 * max(-0.2, min(0.2, c - (a + b) / 2)))
    history_counts.append(3)
data["target_share_trend_pp"] = trends
data["target_share_history_games"] = history_counts

predictions = []
for position in ("TE", "WR"):
    features = model.MODEL_F_FEATURES_BY_POSITION[position]
    for name, columns in (("baseline", features), ("challenger", features + ["target_share_trend_pp"])):
        predictions.append(model.walk_forward_model(data, position, columns, name))

combined = pd.concat(predictions, ignore_index=True)
keys = ["season", "week", "player_id", "position"]
base = combined.loc[combined.model.eq("baseline"), keys + ["actual_ppr", "projected_ppr"]].rename(columns={"projected_ppr": "base"})
chall = combined.loc[combined.model.eq("challenger"), keys + ["projected_ppr"]].rename(columns={"projected_ppr": "chall"})
paired = base.merge(chall, on=keys, validate="one_to_one")
if len(paired) != len(base) or len(paired) != len(chall):
    raise SystemExit("Unmatched baseline and challenger predictions")
paired = paired.merge(data[keys + ["target_share_trend_pp", "target_share_history_games"]], on=keys, validate="one_to_one")
paired["base_error"] = (paired.base - paired.actual_ppr).abs()
paired["chall_error"] = (paired.chall - paired.actual_ppr).abs()
paired["trend_group"] = pd.cut(paired.target_share_trend_pp, [-100, -2, 2, 100], labels=["falling", "stable_or_unknown", "rising"])
print("Matched predictions:", len(paired))
print("Three-appearance trend coverage:", int(paired.target_share_history_games.eq(3).sum()), "of", len(paired))
print("Insufficient history:", int(paired.target_share_history_games.lt(3).sum()))
for name, group in [("ALL", paired), *list(paired.groupby("position")), *[(f"{pos}/{cohort}", g) for (pos, cohort), g in paired.groupby(["position", "trend_group"], observed=True)]]:
    print(f"{name}: n={len(group)} baseline_MAE={group.base_error.mean():.4f} challenger_MAE={group.chall_error.mean():.4f} delta={group.chall_error.mean()-group.base_error.mean():+.4f}")
for name, column in (("baseline", "base"), ("challenger", "chall")):
    ranked = model.add_weekly_ranks(paired[keys + ["actual_ppr", column]].rename(columns={column: "projected_ppr"}), "projected_ppr")
    print(name, "mean absolute rank error:", round(ranked.absolute_rank_error.mean(), 4))
    for position, group in ranked.groupby("position"):
        print(f"  {position}: n={len(group)} mean_absolute_rank_error={group.absolute_rank_error.mean():.4f}")
print("Experimental only. No live data or model files modified.")
