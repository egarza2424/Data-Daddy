"""Read-only TE/WR top-K recall and ranking-miss audit for target-volume challenger."""
import importlib.util
import pandas as pd

spec = importlib.util.spec_from_file_location("model", "scripts/build_ppr_projection_model.py")
model = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model)

data = pd.read_csv("projection-model/2025-historical-ppr-dataset.csv")
stats = pd.read_csv("historical-data/player_stats_2025.csv", low_memory=False)
for frame in (data, stats):
    frame["player_id"] = frame.player_id.astype(str)
    frame["week"] = pd.to_numeric(frame.week)
    frame["season"] = pd.to_numeric(frame.season)
stats["targets"] = pd.to_numeric(stats.targets, errors="coerce").fillna(0)
stats = stats[stats.position.isin(["TE", "WR"])]
histories = {(s, p, t): g.sort_values("week") for (s, p, t), g in stats.groupby(["season", "player_id", "team"])}
average, counts = [], []
for r in data.itertuples(index=False):
    h = histories.get((r.season, r.player_id, r.team))
    prior = h[h.week < r.week].tail(3) if h is not None else None
    n = len(prior) if prior is not None else 0
    counts.append(n)
    average.append(float(prior.targets.mean()) if r.position in ("TE", "WR") and n == 3 else 0.0)
data["prior_target_average"] = average
data["target_history_count"] = counts

frames = []
for pos in ("TE", "WR"):
    features = model.MODEL_F_FEATURES_BY_POSITION[pos]
    for name, cols in (("baseline", features), ("average", features + ["prior_target_average"])):
        frames.append(model.walk_forward_model(data, pos, cols, name))
pred = pd.concat(frames, ignore_index=True)
keys = ["season", "week", "player_id", "position"]
baseline = pred[pred.model == "baseline"][keys + ["actual_ppr", "projected_ppr"]].rename(columns={"projected_ppr": "baseline"})
challenger = pred[pred.model == "average"][keys + ["projected_ppr"]].rename(columns={"projected_ppr": "average"})
paired = baseline.merge(challenger, on=keys, validate="one_to_one").merge(
    data[keys + ["target_history_count", "prior_target_average"]], on=keys, validate="one_to_one")
if len(paired) != len(baseline) or len(paired) != len(challenger):
    raise RuntimeError("Unmatched baseline/challenger predictions")
print("Matched player-weeks:", len(paired))
print("Top-K uses the same eligible players for baseline, challenger and actual in each week.")
for position, group in paired.groupby("position"):
    print("\\n", position)
    limits = (12, 24) if position == "TE" else (12, 24, 36)
    weekly = []
    for (season, week), w in group.groupby(["season", "week"]):
        w = w.copy()
        w["actual_rank"] = w.actual_ppr.rank(method="min", ascending=False)
        for name in ("baseline", "average"):
            w[name + "_rank"] = w[name].rank(method="min", ascending=False)
        weekly.append(w)
    ranked = pd.concat(weekly, ignore_index=True)
    for k in limits:
        print(f"  top-{k} actual-player recall (micro):")
        for name in ("baseline", "average"):
            hits = 0
            total = 0
            for (_, _), w in ranked.groupby(["season", "week"]):
                actual = set(w.nlargest(min(k, len(w)), "actual_ppr").player_id)
                predicted = set(w.nlargest(min(k, len(w)), name).player_id)
                hits += len(actual & predicted)
                total += len(actual)
            print(f"    {name}: {hits}/{total} = {hits/total:.2%}")
    for name in ("baseline", "average"):
        ranked[name + "_rank_error"] = (ranked[name + "_rank"] - ranked.actual_rank).abs()
    ranked["volume_band"] = pd.cut(ranked.prior_target_average, [-0.01, 2, 4, 6, 8, float("inf")],
                                    labels=["0-2", "2-4", "4-6", "6-8", "8+"])
    for band, cohort in ranked[ranked.target_history_count.eq(3)].groupby("volume_band", observed=True):
        print(f"  target average {band}: n={len(cohort)} "
              f"baseline_rank_error={cohort.baseline_rank_error.mean():.3f} "
              f"average_rank_error={cohort.average_rank_error.mean():.3f}")
    misses = ranked.assign(improvement=ranked.baseline_rank_error-ranked.average_rank_error)
    print("  Largest baseline rank misses (descriptive; player IDs):")
    print(misses.nlargest(8, "baseline_rank_error")[["week", "player_id", "actual_ppr", "baseline", "average",
        "actual_rank", "baseline_rank", "average_rank", "prior_target_average"]].to_string(index=False))
print("Historical experiment only; no production changes.")
