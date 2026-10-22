"""Read-only historical Model Confidence calibration audit."""
from pathlib import Path
import pandas as pd

historical = pd.read_csv("projection-model/2025-historical-ppr-dataset.csv")
predictions = pd.read_csv("projection-model/2025-ppr-walkforward-predictions.csv")
required = {"player_id", "week", "position", "model_confidence_score"}
if not required.issubset(historical.columns):
    raise SystemExit("Historical confidence fields unavailable")
if "model" in predictions.columns:
    predictions = predictions[predictions["model"] == "F_position_specific"].copy()
keys = ["player_id", "week", "position"]
if "season" in historical.columns and "season" in predictions.columns:
    keys.append("season")
if historical.duplicated(keys).any() or predictions.duplicated(keys).any():
    raise SystemExit("Duplicate join keys; cannot safely match records")
required_predictions = {"projected_ppr", "actual_ppr"}
if not required_predictions.issubset(predictions.columns):
    raise SystemExit("Frozen prediction or actual fields missing")
joined = historical[keys + ["model_confidence_score"]].merge(
    predictions[keys + ["projected_ppr", "actual_ppr"]],
    on=keys, how="inner", validate="one_to_one")
for col in ["model_confidence_score", "projected_ppr", "actual_ppr"]:
    joined[col] = pd.to_numeric(joined[col], errors="coerce")
joined = joined.dropna(subset=["model_confidence_score", "projected_ppr", "actual_ppr"])
joined = joined[joined.model_confidence_score.between(0, 100)].copy()
joined["absolute_error"] = (joined.actual_ppr - joined.projected_ppr).abs()
joined["confidence_band"] = pd.cut(joined.model_confidence_score, [-0.01, 40, 60, 80, 100], labels=["0-40", "41-60", "61-80", "81-100"])
print("Matched rows:", len(joined))
if joined.empty:
    raise SystemExit("No matched historical rows")
print(joined.groupby(["position", "confidence_band"], observed=True).agg(rows=("absolute_error", "size"), mae=("absolute_error", "mean")).round(3).to_string())
print("Overall:")
print(joined.groupby("confidence_band", observed=True).agg(rows=("absolute_error", "size"), mae=("absolute_error", "mean")).round(3).to_string())
print("Caution: verify confidence features are pregame-only before interpreting calibration.")

# Control for player scoring volume: compare errors within pregame projection tiers.
joined["projection_tier"] = pd.cut(
    joined.projected_ppr, [-float("inf"), 5, 10, 15, 20, float("inf")],
    labels=["<=5", "5-10", "10-15", "15-20", ">20"])
joined["scaled_error"] = joined.absolute_error / joined.projected_ppr.clip(lower=5)
print("\\nProjected PPR and scale-adjusted error by confidence band:")
print(joined.groupby("confidence_band", observed=True).agg(
    rows=("absolute_error", "size"),
    avg_projected_ppr=("projected_ppr", "mean"),
    mae=("absolute_error", "mean"),
    scaled_error=("scaled_error", "mean")).round(3).to_string())
print("\\nMAE within comparable projected-PPR tiers:")
print(joined.groupby(["position", "projection_tier", "confidence_band"], observed=True).agg(
    rows=("absolute_error", "size"), mae=("absolute_error", "mean")).round(3).to_string())
print("Interpret tiers with small row counts cautiously; no model parameters changed.")

# Minimum-sample comparison: require at least 20 observations in each compared band.
MIN_ROWS = 20
tier_summary = joined.groupby(
    ["position", "projection_tier", "confidence_band"], observed=True
).agg(rows=("absolute_error", "size"), mae=("absolute_error", "mean"),
      scaled_error=("scaled_error", "mean")).reset_index()
eligible = tier_summary[tier_summary.rows >= MIN_ROWS].copy()
print("\\nWithin-tier confidence comparisons (minimum 20 rows per band):")
for (position, tier), group in eligible.groupby(["position", "projection_tier"], observed=True):
    if len(group) < 2:
        continue
    print(f"{position} projected {tier}:")
    print(group[["confidence_band", "rows", "mae", "scaled_error"]].round(3).to_string(index=False))
print("Historical provenance: build_historical_ppr_dataset.py specifies prior weeks only;")
print("historical availability is a constant 95, not reconstructed injury information.")
print("Do not treat these observational comparisons as calibrated probabilities.")

# Experimental, read-only role-growth challenger. Reconstruct prior-game workload
# from raw historical stats; do not use target-week observations.
# Load workload inputs without importing the historical build pipeline.
def prepare_workload_stats(frame):
    frame = frame.copy()
    for source, target in [("player_name", "player_display_name"), ("recent_team", "team"), ("passing_attempts", "attempts")]:
        if target not in frame.columns and source in frame.columns:
            frame[target] = frame[source]
    for column in ["carries", "targets", "attempts"]:
        if column not in frame.columns:
            frame[column] = 0
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0)
    frame["opportunity_raw"] = frame["carries"] + frame["targets"]
    qb = frame["position"] == "QB"
    frame.loc[qb, "opportunity_raw"] = frame.loc[qb, "attempts"] + frame.loc[qb, "carries"]
    return frame
from pathlib import Path
stats_path = Path("historical-data/player_stats_2025.csv")
if not stats_path.exists():
    print("Role-growth challenger skipped: historical player_stats_2025.csv unavailable")
else:
    raw = prepare_workload_stats(pd.read_csv(stats_path))
    candidates = []
    for row in joined.itertuples(index=False):
        prior = raw.loc[
            (raw.player_id.astype(str) == str(row.player_id))
            & (raw.week < row.week)
            & (raw.season == getattr(row, "season", 2025))
        ].sort_values("week").tail(3)
        if len(prior) < 3:
            continue
        workload = prior.opportunity_raw.astype(float).tolist()
        baseline = max((workload[0] + workload[1]) / 2, 1)
        growth = (workload[2] - baseline) / baseline
        # Small capped reward for sustained role expansion, not a live model change.
        bonus = min(10.0, max(0.0, growth * 12.0)) if workload[2] >= workload[1] else 0.0
        candidates.append((row.position, row.projected_ppr, row.actual_ppr,
                           row.model_confidence_score, min(100, row.model_confidence_score + bonus)))
    if candidates:
        trial = pd.DataFrame(candidates, columns=["position", "projected", "actual", "baseline", "challenger"])
        trial["error"] = (trial.actual - trial.projected).abs()
        trial["tier"] = pd.cut(trial.projected, [-float("inf"),5,10,15,20,float("inf")])
        print("\\nRole-growth challenger: score-band diagnostics (not a projection-model backtest)")
        for variant in ["baseline", "challenger"]:
            trial["band"] = pd.cut(trial[variant], [-0.01,40,60,80,100])
            print(variant, trial.groupby("band", observed=True).agg(n=("error","size"),mae=("error","mean")).round(3).to_string())
        print("This diagnostic does NOT establish improved predictive accuracy; test downstream model with frozen walk-forward retraining before deployment.")
