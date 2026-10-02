from pathlib import Path

import numpy as np
import pandas as pd


INPUT_PATH = Path(
    "projection-model/2025-historical-ppr-dataset.csv"
)

OUTPUT_DIR = Path("projection-model")

POSITIONS = ["QB", "RB", "WR", "TE"]

FIRST_TEST_WEEK = 7

MODEL_A_FEATURES = [
    "opportunity_score",
    "production_score",
    "usage_score",
    "redzone_score",
    "model_confidence_score",
]

MODEL_B_FEATURES = [
    "production_raw",
    "opportunity_raw",
    "usage_raw",
    "redzone_raw",
    "model_confidence_score",
]
MODEL_C_FEATURES = [
    "opportunity_score",
    "production_score",
    "usage_score",
    "redzone_score",
    "model_confidence_score",
    "scoring_environment_score",
]
def fit_linear_regression(
    train_x,
    train_y,
):
    """
    Ordinary least squares with an intercept.

    Uses numpy only so the workflow does not require
    scikit-learn.
    """

    x = np.asarray(
        train_x,
        dtype=float,
    )

    y = np.asarray(
        train_y,
        dtype=float,
    )

    intercept = np.ones(
        (len(x), 1),
        dtype=float,
    )

    design = np.hstack(
        [intercept, x]
    )

    coefficients = np.linalg.lstsq(
        design,
        y,
        rcond=None,
    )[0]

    return coefficients


def predict_linear_regression(
    test_x,
    coefficients,
):
    x = np.asarray(
        test_x,
        dtype=float,
    )

    intercept = np.ones(
        (len(x), 1),
        dtype=float,
    )

    design = np.hstack(
        [intercept, x]
    )

    return design @ coefficients


def correlation(
    actual,
    predicted,
):
    actual = np.asarray(
        actual,
        dtype=float,
    )

    predicted = np.asarray(
        predicted,
        dtype=float,
    )

    if len(actual) < 2:
        return np.nan

    if np.std(actual) == 0:
        return np.nan

    if np.std(predicted) == 0:
        return np.nan

    return float(
        np.corrcoef(
            actual,
            predicted,
        )[0, 1]
    )


def metrics(
    actual,
    predicted,
):
    actual = np.asarray(
        actual,
        dtype=float,
    )

    predicted = np.asarray(
        predicted,
        dtype=float,
    )

    errors = predicted - actual

    mae = float(
        np.mean(
            np.abs(errors)
        )
    )

    rmse = float(
        np.sqrt(
            np.mean(
                errors ** 2
            )
        )
    )

    corr = correlation(
        actual,
        predicted,
    )

    return {
        "mae": mae,
        "rmse": rmse,
        "correlation": corr,
    }


def add_weekly_ranks(
    frame,
    prediction_column,
):
    frame = frame.copy()

    frame["actual_position_rank"] = (
        frame.groupby(
            ["week", "position"]
        )["actual_ppr"]
        .rank(
            method="min",
            ascending=False,
        )
    )

    frame["projected_position_rank"] = (
        frame.groupby(
            ["week", "position"]
        )[prediction_column]
        .rank(
            method="min",
            ascending=False,
        )
    )

    frame["absolute_rank_error"] = (
        frame[
            "projected_position_rank"
        ]
        - frame[
            "actual_position_rank"
        ]
    ).abs()

    return frame


def walk_forward_model(
    data,
    position,
    feature_columns,
    model_name,
):
    position_data = (
        data[
            data["position"] == position
        ]
        .copy()
        .sort_values(
            ["week", "player_name"]
        )
    )

    weeks = sorted(
        position_data["week"].unique()
    )

    predictions = []

    for test_week in weeks:
        if test_week < FIRST_TEST_WEEK:
            continue

        train = position_data[
            position_data["week"]
            < test_week
        ].copy()

        test = position_data[
            position_data["week"]
            == test_week
        ].copy()

        if train.empty or test.empty:
            continue

        train = train.dropna(
            subset=(
                feature_columns
                + ["actual_ppr"]
            )
        )

        test = test.dropna(
            subset=feature_columns
        )

        if train.empty or test.empty:
            continue

        coefficients = (
            fit_linear_regression(
                train[feature_columns],
                train["actual_ppr"],
            )
        )

        projected = (
            predict_linear_regression(
                test[feature_columns],
                coefficients,
            )
        )

        # Fantasy scoring can occasionally be negative,
        # but a pregame projection below zero is not
        # useful for the product.
        projected = np.maximum(
            projected,
            0.0,
        )

        week_output = test[
            [
                "season",
                "week",
                "player_id",
                "player_name",
                "position",
                "team",
                "actual_ppr",
            ]
        ].copy()

        week_output[
            "projected_ppr"
        ] = projected

        week_output[
            "model"
        ] = model_name

        week_output[
            "training_rows"
        ] = len(train)

        week_output[
            "training_through_week"
        ] = test_week - 1

        predictions.append(
            week_output
        )

    if not predictions:
        return pd.DataFrame()

    result = pd.concat(
        predictions,
        ignore_index=True,
    )

    result = add_weekly_ranks(
        result,
        "projected_ppr",
    )

    return result


def summarize_model(
    predictions,
):
    rows = []

    for (
        model_name,
        position,
    ), group in predictions.groupby(
        ["model", "position"]
    ):
        score_metrics = metrics(
            group["actual_ppr"],
            group["projected_ppr"],
        )

        rows.append(
            {
                "model": model_name,
                "position": position,
                "observations": len(group),
                "mae": round(
                    score_metrics["mae"],
                    4,
                ),
                "rmse": round(
                    score_metrics["rmse"],
                    4,
                ),
                "correlation": round(
                    score_metrics[
                        "correlation"
                    ],
                    4,
                ),
                "mean_absolute_rank_error":
                    round(
                        float(
                            group[
                                "absolute_rank_error"
                            ].mean()
                        ),
                        4,
                    ),
            }
        )

    return pd.DataFrame(rows)


def summarize_by_week(
    predictions,
):
    rows = []

    for (
        model_name,
        position,
        week,
    ), group in predictions.groupby(
        [
            "model",
            "position",
            "week",
        ]
    ):
        score_metrics = metrics(
            group["actual_ppr"],
            group["projected_ppr"],
        )

        rows.append(
            {
                "model": model_name,
                "position": position,
                "week": int(week),
                "observations": len(group),
                "mae": round(
                    score_metrics["mae"],
                    4,
                ),
                "rmse": round(
                    score_metrics["rmse"],
                    4,
                ),
                "correlation": round(
                    score_metrics[
                        "correlation"
                    ],
                    4,
                ),
                "mean_absolute_rank_error":
                    round(
                        float(
                            group[
                                "absolute_rank_error"
                            ].mean()
                        ),
                        4,
                    ),
            }
        )

    return pd.DataFrame(rows)


def validate_input(data):
    required = {
        "season",
        "week",
        "player_id",
        "player_name",
        "position",
        "team",
        "actual_ppr",
        *MODEL_A_FEATURES,
        *MODEL_B_FEATURES,
        *MODEL_C_FEATURES,    
    }

    missing = sorted(
        required - set(data.columns)
    )

    if missing:
        raise ValueError(
            "Historical dataset is missing "
            f"required columns: {missing}"
        )

    duplicate_count = (
        data.duplicated(
            subset=[
                "season",
                "week",
                "player_id",
            ]
        ).sum()
    )

    if duplicate_count:
        raise ValueError(
            "Historical dataset contains "
            f"{duplicate_count} duplicate "
            "player-week rows."
        )


def main():
    if not INPUT_PATH.exists():
        raise FileNotFoundError(
            f"Input dataset not found: "
            f"{INPUT_PATH}"
        )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    data = pd.read_csv(
        INPUT_PATH
    )

    validate_input(data)

    data = data[
        data["position"].isin(
            POSITIONS
        )
    ].copy()

    prediction_frames = []

    for position in POSITIONS:
        print(
            "\n"
            + "=" * 60
        )
        print(
            f"POSITION: {position}"
        )
        print(
            "=" * 60
        )

        model_a = walk_forward_model(
            data=data,
            position=position,
            feature_columns=(
                MODEL_A_FEATURES
            ),
            model_name=(
                "A_normalized_signals"
            ),
        )

        model_b = walk_forward_model(
            data=data,
            position=position,
            feature_columns=(
                MODEL_B_FEATURES
            ),
            model_name=(
                "B_raw_features"
            ),
        )
        model_c = walk_forward_model(
            data=data,
            position=position,
            feature_columns=(
                MODEL_C_FEATURES
            ),
            model_name=(
                "C_normalized_plus_scoring_environment"
            ),
        )        
        prediction_frames.extend(
            [
                model_a,
                model_b,
                model_c,
            ]
        )
    predictions = pd.concat(
        [
            frame
            for frame in prediction_frames
            if not frame.empty
        ],
        ignore_index=True,
    )

    summary = summarize_model(
        predictions
    )

    weekly_summary = summarize_by_week(
        predictions
    )

    predictions_path = (
        OUTPUT_DIR
        / "2025-ppr-walkforward-predictions.csv"
    )

    summary_path = (
        OUTPUT_DIR
        / "2025-ppr-walkforward-summary.csv"
    )

    weekly_path = (
        OUTPUT_DIR
        / "2025-ppr-walkforward-weekly.csv"
    )

    predictions.to_csv(
        predictions_path,
        index=False,
    )

    summary.to_csv(
        summary_path,
        index=False,
    )

    weekly_summary.to_csv(
        weekly_path,
        index=False,
    )

    print(
        "\nOVERALL WALK-FORWARD RESULTS"
    )

    print(
        summary.to_string(
            index=False
        )
    )

    print(
        "\nSaved:"
    )

    print(
        f"  {predictions_path}"
    )

    print(
        f"  {summary_path}"
    )

    print(
        f"  {weekly_path}"
    )


if __name__ == "__main__":
    main()
