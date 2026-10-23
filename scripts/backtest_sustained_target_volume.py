"""Read-only sustained receiving-target volume experiment."""
import importlib.util
import pandas as pd

spec = importlib.util.spec_from_file_location("model", "scripts/build_ppr_projection_model.py")
model = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model)

data = pd.read_csv("projection-model/2025-historical-ppr-dataset.csv")
stats = pd.read_csv("historical-data/player_stats_2025.csv", low_memory=False)
for frame in (data, stats):
    frame["player_id"] = frame["player_id"].astype(str)
    frame["week"] = pd.to_numeric(frame["week"])
    frame["season"] = pd.to_numeric(frame["season"])
stats["targets"] = pd.to_numeric(stats["targets"], errors="coerce").fillna(0)
stats = stats[stats.position.isin(["WR", "TE"])]
history = {(season, pid, team): g.sort_values("week")
           for (season, pid, team), g in stats.groupby(["season", "player_id", "team"])}

averages, minimums, counts = [], [], []
for r in data.itertuples(index=False):
    h = history.get((r.season, r.player_id, r.team))
    prior = h[h.week < r.week].tail(3) if h is not None else None
    n = len(prior) if prior is not None else 0
    counts.append(n)
    if r.position not in ("WR", "TE") or n < 3:
        averages.append(0.0)
        minimums.append(0.0)
    else:
        averages.append(float(prior.targets.mean()))
        minimums.append(float(prior.targets.min()))
data["prior_target_average"] = averages
data["prior_target_minimum"] = minimums
data["target_history_count"] = counts

outputs = []
for position in ("WR", "TE"):
    base = model.MODEL_F_FEATURES_BY_POSITION[position]
    for label, features in (
        ("baseline", base),
        ("average", base + ["prior_target_average"]),
        ("sustained", base + ["prior_target_minimum"]),
    ):
        frame = model.walk_forward_model(data, position, features, label)
        if frame.empty:
            raise RuntimeError(f"No results for {position} {label}")
        outputs.append(frame)
predictions = pd.concat(outputs, ignore_index=True)
keys = ["season", "week", "player_id", "position"]
paired = predictions[predictions.model == "baseline"][keys + ["actual_ppr", "projected_ppr"]].rename(columns={"projected_ppr": "baseline"})
for label in ("average", "sustained"):
    other = predictions[predictions.model == label][keys + ["projected_ppr"]].rename(columns={"projected_ppr": label})
    paired = paired.merge(other, on=keys, validate="one_to_one")
paired = paired.merge(data[keys + ["target_history_count", "prior_target_minimum"]], on=keys, validate="one_to_one")
if len(paired) != len(predictions[predictions.model == "baseline"]):
    raise RuntimeError("Paired sample mismatch")
print("Matched predictions:", len(paired))
print("Complete three-appearance histories:", int((paired.target_history_count == 3).sum()))
for position, group in [("ALL", paired), *list(paired.groupby("position"))]:
    print(position, "n=", len(group))
    for label in ("baseline", "average", "sustained"):
        mae = (group[label] - group.actual_ppr).abs().mean()
        ranked = model.add_weekly_ranks(group[keys + ["actual_ppr", label]].rename(columns={label: "projected_ppr"}), "projected_ppr")
        print(f"  {label}: MAE={mae:.4f}, rank_error={ranked.absolute_rank_error.mean():.4f}")
for position, group in paired[paired.target_history_count == 3].groupby("position"):
    print(position, "sustained target cohorts")
    bands = pd.cut(group.prior_target_minimum, [-1, 1, 3, 5, 8, float("inf")], labels=["0-1", "2-3", "4-5", "6-8", "9+"])
    for band, cohort in group.groupby(bands, observed=True):
        print(f"  {band}: n={len(cohort)}, actual_PPR={cohort.actual_ppr.mean():.3f}, " +
              ", ".join(f"{label}_MAE={(cohort[label]-cohort.actual_ppr).abs().mean():.4f}" for label in ("baseline", "average", "sustained")))
print("Experiment only; production unchanged.")
