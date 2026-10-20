"""Walk-forward RB component challenger vs unchanged Model F.

Reads the existing historical CSV; writes only separate Model I validation files.
No changes to production models or frozen projections.
"""
from pathlib import Path
import numpy as np
import pandas as pd

SOURCE = Path("projection-model/2025-historical-ppr-dataset.csv")
OUT = Path("projection-model/validation")
BASELINE = [
    "opportunity_score", "production_score", "usage_score",
    "redzone_score", "model_confidence_score",
]
NEEDED = BASELINE + [
    "season", "week", "player_id", "player_name", "position",
    "actual_ppr", "rb_prior_games", "rb_carries_pg",
    "rb_targets_pg", "rb_receptions_pg", "rb_rush_yards_pg",
    "rb_receiving_yards_pg", "rb_redzone_carries_pg",
    "rb_redzone_targets_pg", "implied_team_total",
]


def ols(train_x, train_y, test_x):
    a = np.column_stack([np.ones(len(train_x)), np.asarray(train_x, float)])
    b = np.column_stack([np.ones(len(test_x)), np.asarray(test_x, float)])
    coefficients = np.linalg.lstsq(a, np.asarray(train_y, float), rcond=None)[0]
    return np.maximum(0, b @ coefficients)


def components(frame, rush_prior, catch_prior, rec_prior):
    """All inputs represent prior games or the scheduled game's implied points."""
    f = frame
    carries = f["rb_carries_pg"].to_numpy(float)
    targets = f["rb_targets_pg"].to_numpy(float)
    receptions = f["rb_receptions_pg"].to_numpy(float)
    rush_yards = f["rb_rush_yards_pg"].to_numpy(float)
    rec_yards = f["rb_receiving_yards_pg"].to_numpy(float)
    n = f["rb_prior_games"].to_numpy(float)
    # Approximate attempt-level sample size from prior-game averages.
    rush_attempts = np.maximum(0, carries * n)
    target_attempts = np.maximum(0, targets * n)
    catch_count = np.maximum(0, receptions * n)
    ypc = (rush_yards * n + 40 * rush_prior) / (rush_attempts + 40)
    catch_rate = (catch_count + 25 * catch_prior) / (target_attempts + 25)
    ypr = (rec_yards * n + 20 * rec_prior) / (catch_count + 20)
    rush_points = carries * ypc * 0.1
    receiving_points = targets * catch_rate * (1 + 0.1 * ypr)
    return np.column_stack([
        rush_points,
        receiving_points,
        f["rb_redzone_carries_pg"].to_numpy(float),
        f["rb_redzone_targets_pg"].to_numpy(float),
        f["implied_team_total"].to_numpy(float),
    ])


def training_priors(train):
    n = train["rb_prior_games"].to_numpy(float)
    carries = train["rb_carries_pg"].to_numpy(float) * n
    targets = train["rb_targets_pg"].to_numpy(float) * n
    catches = train["rb_receptions_pg"].to_numpy(float) * n
    rush = train["rb_rush_yards_pg"].to_numpy(float) * n
    receiving = train["rb_receiving_yards_pg"].to_numpy(float) * n
    return (
        np.sum(rush) / max(np.sum(carries), 1),
        np.clip(np.sum(catches) / max(np.sum(targets), 1), 0, 1),
        np.sum(receiving) / max(np.sum(catches), 1),
    )


def main():
    data = pd.read_csv(SOURCE)
    missing = sorted(set(NEEDED) - set(data.columns))
    if missing:
        raise ValueError(f"Missing dataset columns: {missing}")
    rb = data.loc[data["position"].eq("RB")].copy()
    if rb[NEEDED].isna().any().any():
        raise ValueError("RB data has missing required values")
    if rb.duplicated(["season", "week", "player_id"]).any():
        raise ValueError("Duplicate player-week records")
    rows = []
    for week in sorted(rb["week"].unique()):
        if week < 7:
            continue
        train = rb.loc[rb["week"] < week].copy()
        test = rb.loc[rb["week"] == week].copy()
        if train.empty or test.empty:
            continue
        y = train["actual_ppr"].to_numpy(float)
        baseline = ols(train[BASELINE], y, test[BASELINE])
        priors = training_priors(train)
        challenger = ols(
            components(train, *priors),
            y,
            components(test, *priors),
        )
        for model, values in [
            ("F_position_specific", baseline),
            ("I_RB_component", challenger),
        ]:
            part = test[["season", "week", "player_id", "player_name", "actual_ppr"]].copy()
            part["model"] = model
            part["projected_ppr"] = values
            part["training_through_week"] = week - 1
            part["training_rows"] = len(train)
            rows.append(part)
    predictions = pd.concat(rows, ignore_index=True)
    predictions["actual_rank"] = predictions.groupby(["model", "week"])["actual_ppr"].rank(
        method="min", ascending=False
    )
    predictions["projected_rank"] = predictions.groupby(["model", "week"])["projected_ppr"].rank(
        method="min", ascending=False
    )
    predictions["absolute_rank_error"] = (
        predictions["actual_rank"] - predictions["projected_rank"]
    ).abs()
    summaries = []
    for model, group in predictions.groupby("model"):
        error = group["projected_ppr"].to_numpy() - group["actual_ppr"].to_numpy()
        summaries.append({
            "model": model,
            "observations": len(group),
            "mae": round(float(np.abs(error).mean()), 4),
            "rmse": round(float(np.sqrt(np.mean(error ** 2))), 4),
            "correlation": round(float(group["projected_ppr"].corr(group["actual_ppr"])), 4),
            "mean_absolute_rank_error": round(float(group["absolute_rank_error"].mean()), 4),
        })
    summary = pd.DataFrame(summaries)
    OUT.mkdir(parents=True, exist_ok=True)
    predictions.to_csv(OUT / "2025-rb-model-i-predictions.csv", index=False)
    summary.to_csv(OUT / "2025-rb-model-i-summary.csv", index=False)
    print(summary.to_string(index=False))
    print("Saved validation outputs only; production files unchanged.")


if __name__ == "__main__":
    main()
