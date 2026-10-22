"""Read-only opportunity signal diagnostic using frozen 2025 Model F predictions."""
import pandas as pd

historical = pd.read_csv("projection-model/2025-historical-ppr-dataset.csv")
predictions = pd.read_csv("projection-model/2025-ppr-walkforward-predictions.csv")
predictions = predictions.loc[predictions.model.eq("F_position_specific")].copy()
keys = ["season", "week", "player_id", "position"]
required = keys + ["opportunity_score", "opportunity_raw", "actual_ppr"]
for col in required:
    if col not in historical:
        raise SystemExit(f"Missing historical field: {col}")
for frame in (historical, predictions):
    frame["player_id"] = frame.player_id.astype(str)
if historical.duplicated(keys).any() or predictions.duplicated(keys).any():
    raise SystemExit("Duplicate player-week keys")
joined = historical[required].merge(
    predictions[keys + ["projected_ppr"]],
    on=keys, how="inner", validate="one_to_one")
joined = joined.dropna(subset=["opportunity_score", "opportunity_raw", "actual_ppr", "projected_ppr"]).copy()
joined["absolute_error"] = (joined.actual_ppr - joined.projected_ppr).abs()
joined["scaled_error"] = joined.absolute_error / joined.projected_ppr.clip(lower=5)
joined["opportunity_band"] = pd.cut(
    joined.opportunity_score, [-float("inf"), 20, 40, 60, 80, float("inf")],
    labels=["<=20", "21-40", "41-60", "61-80", ">80"])
joined["projection_tier"] = pd.cut(
    joined.projected_ppr, [-float("inf"), 5, 10, 15, 20, float("inf")],
    labels=["<=5", "5-10", "10-15", "15-20", ">20"])
print("Matched historical Model F predictions:", len(joined))
print("Opportunity score bands by position:")
print(joined.groupby(["position", "opportunity_band"], observed=True).agg(
    n=("absolute_error", "size"), avg_opportunity=("opportunity_raw", "mean"),
    avg_actual_ppr=("actual_ppr", "mean"), avg_projected_ppr=("projected_ppr", "mean"),
    mae=("absolute_error", "mean"), scaled_error=("scaled_error", "mean")).round(3).to_string())
print("\\nComparable position / projection tiers (minimum 20 observations):")
groups = joined.groupby(["position", "projection_tier", "opportunity_band"], observed=True).agg(
    n=("absolute_error", "size"), mae=("absolute_error", "mean"),
    scaled_error=("scaled_error", "mean")).reset_index()
print(groups.loc[groups.n >= 20].round(3).to_string(index=False))
print("\\nDiagnostic only. Observational group differences are not proof of predictive improvement.")
print("No live AI Score, weights, rankings or projections changed.")
