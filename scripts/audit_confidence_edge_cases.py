"""Pregame-only confidence edge-case audit: sparse history, missed weeks, role expansion."""
import pandas as pd
from pathlib import Path
hist = pd.read_csv("projection-model/2025-historical-ppr-dataset.csv")
pred = pd.read_csv("projection-model/2025-ppr-walkforward-predictions.csv")
pred = pred.loc[pred.model.eq("F_position_specific")].copy()
keys = ["season", "week", "player_id", "position"]
for frame in (hist, pred):
    frame["player_id"] = frame.player_id.astype(str)
joined = hist[keys + ["model_confidence_score"]].merge(
    pred[keys + ["projected_ppr", "actual_ppr"]], on=keys, validate="one_to_one")
stats = pd.read_csv("historical-data/player_stats_2025.csv", low_memory=False)
stats["player_id"] = stats.player_id.astype(str)
for col in ["week", "season", "carries", "targets"]:
    stats[col] = pd.to_numeric(stats[col], errors="coerce").fillna(0)
if "attempts" not in stats:
    stats["attempts"] = stats["passing_attempts"]
stats["attempts"] = pd.to_numeric(stats.attempts, errors="coerce").fillna(0)
stats["workload"] = stats.carries + stats.targets
stats.loc[stats.position.eq("QB"), "workload"] = stats.attempts + stats.carries
stats = stats.loc[stats.position.isin(["QB", "RB", "WR", "TE"])]
groups = {(season, pid): g.sort_values("week") for (season, pid), g in stats.groupby(["season", "player_id"])}
labels = []
for row in joined.itertuples(index=False):
    prior = groups.get((row.season, row.player_id))
    if prior is None:
        labels.append("No prior recorded games")
        continue
    prior = prior.loc[prior.week.lt(row.week)].tail(3)
    if len(prior) < 3:
        labels.append("1-2 prior games" if len(prior) else "No prior recorded games")
    elif row.week - int(prior.week.max()) > 1:
        labels.append("Gap since last recorded game")
    else:
        a, b, c = prior.workload.astype(float).tolist()
        if c >= b and c > (a + b) / 2 * 1.5 and c >= 5:
            labels.append("Recent workload expansion")
        else:
            labels.append("Established / other")
joined["case"] = labels
joined["absolute_error"] = (joined.projected_ppr - joined.actual_ppr).abs()
joined["scaled_error"] = joined.absolute_error / joined.projected_ppr.clip(lower=5)
print("Pregame history-based cohorts; missed-week gaps do NOT prove injury; sparse history does NOT prove rookie status.")
print(joined.groupby(["position", "case"]).agg(rows=("absolute_error", "size"), confidence=("model_confidence_score", "mean"), projected=("projected_ppr", "mean"), mae=("absolute_error", "mean"), scaled_error=("scaled_error", "mean")).round(3).to_string())
print("\\nTotal observations:", len(joined))
print("Diagnostic only. No live model changes.")
