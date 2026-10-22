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
