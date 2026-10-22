"""Read-only, pregame role-transition confidence challenger with paired walk-forward tests.

Fixed hypotheses, no coefficient tuning: penalize sparse history, missed-week gaps,
and abrupt workload changes. A gap is not proof of injury or absence from roster.
"""
import importlib.util
import pandas as pd

spec = importlib.util.spec_from_file_location("ppr_model", "scripts/build_ppr_projection_model.py")
model = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model)
data = pd.read_csv("projection-model/2025-historical-ppr-dataset.csv")
stats = pd.read_csv("historical-data/player_stats_2025.csv", low_memory=False).copy()
for col in ("carries", "targets", "week", "season"):
    if col not in stats:
        raise SystemExit(f"Missing historical stat: {col}")
    stats[col] = pd.to_numeric(stats[col], errors="coerce").fillna(0)
if "attempts" not in stats:
    if "passing_attempts" not in stats:
        raise SystemExit("Missing QB passing attempts")
    stats["attempts"] = stats["passing_attempts"]
stats["attempts"] = pd.to_numeric(stats.attempts, errors="coerce").fillna(0)
stats["workload"] = stats.carries + stats.targets
stats.loc[stats.position.eq("QB"), "workload"] = stats.attempts + stats.carries
stats["player_id"] = stats.player_id.astype(str)
data["player_id"] = data.player_id.astype(str)

# All features use weeks strictly earlier than each target week.
history = {(season, pid): group.sort_values("week")
           for (season, pid), group in stats.groupby(["season", "player_id"])}
adjustments = []
categories = []
for row in data.itertuples(index=False):
    group = history.get((row.season, row.player_id))
    prior = group.loc[group.week.lt(row.week)].tail(3) if group is not None else None
    count = 0 if prior is None else len(prior)
    if count < 3:
        category, penalty = "sparse_history", 8.0
    elif row.week - int(prior.week.max()) > 1:
        category, penalty = "missed_week_gap", 6.0
    else:
        a, b, c = prior.workload.astype(float).tolist()
        reference = max((a + b) / 2, 1.0)
        if c >= b and c >= 5 and c > reference * 1.5:
            category, penalty = "workload_expansion", 8.0 if row.position == "QB" else 5.0
        else:
            category, penalty = "established", 0.0
    categories.append(category)
    adjustments.append(penalty)
data["transition_case"] = categories
data["transition_penalty"] = adjustments
data["confidence_transition"] = (data.model_confidence_score - data.transition_penalty).clip(lower=0)
print("Fixed experimental confidence penalties; no training or test-week data leakage.")
print(data.transition_case.value_counts().to_string())

frames = []
for position in model.POSITIONS:
    features = model.MODEL_F_FEATURES_BY_POSITION[position]
    for name, confidence in (("baseline", "model_confidence_score"), ("transition", "confidence_transition")):
        selected = [confidence if f == "model_confidence_score" else f for f in features]
        prediction = model.walk_forward_model(data, position, selected, name)
        if prediction.empty:
            raise SystemExit(f"Empty predictions for {position}/{name}")
        frames.append(prediction)
all_predictions = pd.concat(frames, ignore_index=True)
keys = ["season", "week", "player_id", "position"]
base = all_predictions.loc[all_predictions.model.eq("baseline")].set_index(keys)
chall = all_predictions.loc[all_predictions.model.eq("transition")].set_index(keys)
paired = base[["projected_ppr", "actual_ppr"]].rename(columns={"projected_ppr": "base_ppr"}).join(
    chall[["projected_ppr"]].rename(columns={"projected_ppr": "transition_ppr"}),
    how="inner", validate="one_to_one").reset_index()
if len(paired) != len(base) or len(paired) != len(chall):
    raise SystemExit("Unpaired predictions; refusing misleading comparison")
cohorts = data[keys + ["transition_case"]].drop_duplicates(keys)
paired = paired.merge(cohorts, on=keys, how="left", validate="one_to_one")
paired["base_error"] = (paired.base_ppr - paired.actual_ppr).abs()
paired["transition_error"] = (paired.transition_ppr - paired.actual_ppr).abs()
print("\\nPAIRED WALK-FORWARD MAE (lower is better)")
for label, group in [("ALL", paired), *list(paired.groupby("position")),
                     *[(f"COHORT {case}", g) for case, g in paired.groupby("transition_case")]]:
    print(f"{label}: n={len(group)}, baseline={group.base_error.mean():.4f}, transition={group.transition_error.mean():.4f}, delta={group.transition_error.mean()-group.base_error.mean():+.4f}")
for name, col in (("baseline", "base_ppr"), ("transition", "transition_ppr")):
    ranks = model.add_weekly_ranks(paired[keys + ["actual_ppr", col]].rename(columns={col: "projected_ppr"}), "projected_ppr")
    print(f"{name} mean absolute rank error: {ranks.absolute_rank_error.mean():.4f}")
print("Experimental only; no live rankings, weights, or projections changed.")
