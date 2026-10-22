"""Read-only paired walk-forward test of a prior-week role-growth confidence bonus."""
import importlib.util
from pathlib import Path
import numpy as np
import pandas as pd

spec = importlib.util.spec_from_file_location("ppr_model", "scripts/build_ppr_projection_model.py")
model = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model)
data = pd.read_csv("projection-model/2025-historical-ppr-dataset.csv")
stats = pd.read_csv("historical-data/player_stats_2025.csv", low_memory=False)
for col in ("carries", "targets", "attempts", "week", "season"):
    if col not in stats.columns:
        if col == "attempts" and "passing_attempts" in stats.columns:
            stats[col] = stats.passing_attempts
        else:
            raise SystemExit(f"Missing raw history column: {col}")
    stats[col] = pd.to_numeric(stats[col], errors="coerce").fillna(0)
stats["workload"] = stats.carries + stats.targets
stats.loc[stats.position == "QB", "workload"] = stats.attempts + stats.carries
stats["player_id"] = stats.player_id.astype(str)
data["player_id"] = data.player_id.astype(str)
# Calculate bonuses for every training and test row from strictly earlier weeks.
bonuses = {}
for (season, player_id), group in stats.groupby(["season", "player_id"]):
    ordered = group.sort_values("week")
    for week in data.loc[(data.season == season) & (data.player_id == player_id), "week"].unique():
        prior = ordered.loc[ordered.week < week].tail(3)
        bonus = 0.0
        if len(prior) == 3:
            a, b, c = prior.workload.astype(float).tolist()
            growth = (c - (a + b) / 2) / max((a + b) / 2, 1)
            if c >= b:
                bonus = min(10.0, max(0.0, growth * 12.0))
        bonuses[(season, player_id, week)] = bonus
data["growth_bonus"] = [bonuses.get((r.season, r.player_id, r.week), 0.0) for r in data.itertuples()]
data["confidence_challenger"] = (data.model_confidence_score + data.growth_bonus).clip(upper=100)
print("Rows with positive role bonus:", int((data.growth_bonus > 0).sum()))
results = []
for position in model.POSITIONS:
    original = model.MODEL_F_FEATURES_BY_POSITION[position]
    for name, col in (("baseline", "model_confidence_score"), ("challenger", "confidence_challenger")):
        features = [col if x == "model_confidence_score" else x for x in original]
        pred = model.walk_forward_model(data, position, features, name)
        if pred.empty:
            raise SystemExit(f"No predictions: {position} {name}")
        results.append(pred)
combined = pd.concat(results, ignore_index=True)
keys = ["season", "week", "player_id", "position"]
base = combined[combined.model == "baseline"].set_index(keys)
chall = combined[combined.model == "challenger"].set_index(keys)
paired = base[["projected_ppr", "actual_ppr"]].join(chall[["projected_ppr"]], how="inner", lsuffix="_base", rsuffix="_chall", validate="one_to_one").reset_index()
paired["base_error"] = (paired.projected_ppr_base - paired.actual_ppr).abs()
paired["chall_error"] = (paired.projected_ppr_chall - paired.actual_ppr).abs()
print("Paired predictions:", len(paired))
for position, group in [("ALL", paired), *list(paired.groupby("position"))]:
    print(f"{position}: rows={len(group)}, baseline_MAE={group.base_error.mean():.4f}, challenger_MAE={group.chall_error.mean():.4f}, delta={group.chall_error.mean()-group.base_error.mean():+.4f}")
for name, column in (("baseline", "projected_ppr_base"), ("challenger", "projected_ppr_chall")):
    ranked = model.add_weekly_ranks(paired.rename(columns={column:"projected_ppr"}), "projected_ppr")
    print(name, "mean absolute rank error:", round(ranked.absolute_rank_error.mean(), 4))
print("Experimental only; no deployment or production file writes.")
