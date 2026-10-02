from pathlib import Path
import re

import numpy as np
import pandas as pd


HISTORICAL_PATH = Path(
    "projection-model/2025-historical-ppr-dataset.csv"
)

LIVE_SNAPSHOT_PATH = Path(
    "projection-model/current-live-model-snapshot.csv"
)
OUTPUT_DIR = Path("projection-model")

POSITIONS = ["QB", "RB", "WR", "TE"]


CORE_FEATURES = [
    "opportunity_score",
    "production_score",
    "usage_score",
    "redzone_score",
    "model_confidence_score",
]

MODEL_F_FEATURES = {
    "QB": [
        *CORE_FEATURES,
        "matchup_score",
    ],
    "RB": [
        *CORE_FEATURES,
    ],
    "WR": [
        *CORE_FEATURES,
    ],
    "TE": [
        *CORE_FEATURES,
        "matchup_score",
        "scoring_environment_score",
    ],
}


def fit_linear_regression(
    train_x,
    train_y,
):
    """
    Ordinary least squares with an intercept.

    This intentionally matches the regression method
    used by the frozen historical backtest.
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


def snapshot_week(path):
    match = re.search(
        r"2026-week(\d+)-pregame-model-snapshot\.csv$",
        path.name,
    )

    if not match:
        return -1

    return int(match.group(1))


def find_latest_snapshot():
    if not LIVE_SNAPSHOT_PATH.exists():
        raise RuntimeError(
            "Live production snapshot not found: "
            f"{LIVE_SNAPSHOT_PATH}"
        )

    snapshot = pd.read_csv(
        LIVE_SNAPSHOT_PATH
    )

    if "snapshot_week" not in snapshot.columns:
        raise RuntimeError(
            "Live production snapshot is missing "
            "snapshot_week."
        )

    weeks = (
        pd.to_numeric(
            snapshot["snapshot_week"],
            errors="coerce",
        )
        .dropna()
        .astype(int)
        .unique()
        .tolist()
    )

    if len(weeks) != 1:
        raise RuntimeError(
            "Could not determine one NFL week "
            "from live production snapshot: "
            f"{weeks}"
        )

    week = weeks[0]

    if week <= 0:
        raise RuntimeError(
            f"Invalid snapshot week: {week}"
        )

    return LIVE_SNAPSHOT_PATH, week

def validate_historical(
    historical,
):
    required = {
        "position",
        "actual_ppr",
    }

    for features in MODEL_F_FEATURES.values():
        required.update(features)

    missing = sorted(
        required - set(historical.columns)
    )

    if missing:
        raise RuntimeError(
            "Historical dataset is missing columns: "
            + ", ".join(missing)
        )


def validate_snapshot(
    snapshot,
):
    required = {
        "snapshot_week",
        "player_id",
        "player_name",
        "position",
        "team",
        "opponent",
        "model_score",
        "position_rank",
        "opportunity_score",
        "production_score",
        "usage_score",
        "redzone_score",
        "matchup_score",
        "scoring_environment_score",
    }

    missing = sorted(
        required - set(snapshot.columns)
    )

    if missing:
        raise RuntimeError(
            "Snapshot is missing columns: "
            + ", ".join(missing)
        )


def prepare_snapshot(
    snapshot,
):
    snapshot = snapshot.copy()

    snapshot["position"] = (
        snapshot["position"]
        .astype(str)
        .str.upper()
        .str.strip()
    )

    snapshot = snapshot[
        snapshot["position"].isin(POSITIONS)
    ].copy()

    # Historical Model F uses model_confidence_score.
    # The live snapshot currently exports this signal
    # under expert_score.
    if (
        "model_confidence_score"
        not in snapshot.columns
    ):
        if "expert_score" not in snapshot.columns:
            raise RuntimeError(
                "Snapshot contains neither "
                "model_confidence_score nor expert_score."
            )

        snapshot[
            "model_confidence_score"
        ] = pd.to_numeric(
            snapshot["expert_score"],
            errors="coerce",
        )

    return snapshot


def build_position_projection(
    historical,
    snapshot,
    position,
):
    features = MODEL_F_FEATURES[position]

    train = historical[
        historical["position"] == position
    ].copy()

    current = snapshot[
        snapshot["position"] == position
    ].copy()

    if train.empty:
        raise RuntimeError(
            f"No historical training rows for {position}."
        )

    if current.empty:
        print(
            f"{position}: no current snapshot rows."
        )

        return (
            current,
            [],
        )

    numeric_columns = (
        features
        + ["actual_ppr"]
    )

    for column in numeric_columns:
        train[column] = pd.to_numeric(
            train[column],
            errors="coerce",
        )

    for column in features:
        current[column] = pd.to_numeric(
            current[column],
            errors="coerce",
        )

    train = train.dropna(
        subset=(
            features
            + ["actual_ppr"]
        )
    )

    if train.empty:
        raise RuntimeError(
            f"No valid training rows for {position}."
        )

    missing_current = (
        current[features]
        .isna()
        .any(axis=1)
    )

    if missing_current.any():
        problem_players = (
            current.loc[
                missing_current,
                "player_name",
            ]
            .astype(str)
            .tolist()
        )

        raise RuntimeError(
            f"{position} snapshot has missing "
            "Model F features for: "
            + ", ".join(problem_players[:20])
        )

    coefficients = fit_linear_regression(
        train[features],
        train["actual_ppr"],
    )

    projected = predict_linear_regression(
        current[features],
        coefficients,
    )

    current["projected_ppr"] = (
        np.maximum(
            projected,
            0.0,
        )
    )

    current["projected_ppr"] = (
        current["projected_ppr"]
        .round(2)
    )

    current["projected_position_rank"] = (
        current["projected_ppr"]
        .rank(
            method="min",
            ascending=False,
        )
        .astype(int)
    )

    coefficient_rows = [
        {
            "position": position,
            "feature": "intercept",
            "coefficient": coefficients[0],
            "training_rows": len(train),
        }
    ]

    coefficient_rows.extend(
        {
            "position": position,
            "feature": feature,
            "coefficient": coefficient,
            "training_rows": len(train),
        }
        for feature, coefficient in zip(
            features,
            coefficients[1:],
        )
    )

    print(
        f"{position}: "
        f"{len(train)} training rows, "
        f"{len(current)} projections"
    )

    return (
        current,
        coefficient_rows,
    )


def main():
    if not HISTORICAL_PATH.exists():
        raise RuntimeError(
            f"Historical dataset not found: "
            f"{HISTORICAL_PATH}"
        )

    snapshot_path, target_week = (
        find_latest_snapshot()
    )

    print(
        f"Historical training data: "
        f"{HISTORICAL_PATH}"
    )

    print(
        f"Current snapshot: {snapshot_path}"
    )

    print(
        f"Target NFL Week: {target_week}"
    )

    historical = pd.read_csv(
        HISTORICAL_PATH
    )

    snapshot = pd.read_csv(
        snapshot_path
    )

    validate_historical(
        historical
    )

    validate_snapshot(
        snapshot
    )

    snapshot = prepare_snapshot(
        snapshot
    )

    snapshot_weeks = (
        pd.to_numeric(
            snapshot["snapshot_week"],
            errors="coerce",
        )
        .dropna()
        .astype(int)
        .unique()
        .tolist()
    )

    if snapshot_weeks != [target_week]:
        raise RuntimeError(
            "Snapshot week column does not match "
            f"filename week {target_week}: "
            f"{snapshot_weeks}"
        )

    projection_frames = []
    coefficient_rows = []

    for position in POSITIONS:
        projected, coefficients = (
            build_position_projection(
                historical=historical,
                snapshot=snapshot,
                position=position,
            )
        )

        if not projected.empty:
            projection_frames.append(
                projected
            )

        coefficient_rows.extend(
            coefficients
        )

    if not projection_frames:
        raise RuntimeError(
            "No weekly projections were generated."
        )

    projections = pd.concat(
        projection_frames,
        ignore_index=True,
    )

    projections["projection_model"] = (
        "F_position_specific"
    )

    projections["projection_training_season"] = (
        2025
    )

    projections = projections.sort_values(
        [
            "position",
            "projected_position_rank",
            "player_name",
        ]
    ).reset_index(
        drop=True
    )

    output_columns = [
        "snapshot_week",
        "player_id",
        "player_name",
        "position",
        "team",
        "opponent",
        "model_score",
        "position_rank",
        "projected_ppr",
        "projected_position_rank",
        "opportunity_score",
        "production_score",
        "usage_score",
        "redzone_score",
        "model_confidence_score",
        "matchup_score",
        "scoring_environment_score",
        "projection_model",
        "projection_training_season",
    ]

    projections = projections[
        output_columns
    ]

    coefficients = pd.DataFrame(
        coefficient_rows
    )

    coefficients[
        "coefficient"
    ] = coefficients[
        "coefficient"
    ].round(8)

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    projection_path = (
        OUTPUT_DIR
        / (
            f"2026-week{target_week}-"
            "ppr-projections.csv"
        )
    )

    coefficient_path = (
        OUTPUT_DIR
        / (
            f"2026-week{target_week}-"
            "ppr-model-coefficients.csv"
        )
    )

    projections.to_csv(
        projection_path,
        index=False,
    )

    coefficients.to_csv(
        coefficient_path,
        index=False,
    )

    print()
    print(
        f"Wrote {len(projections)} projections "
        f"to {projection_path}"
    )

    print(
        f"Wrote coefficient audit to "
        f"{coefficient_path}"
    )

    print()
    print("Projection counts:")
    print(
        projections[
            "position"
        ]
        .value_counts()
        .sort_index()
        .to_string()
    )

    print()
    print("Top 10 projections by position:")

    for position in POSITIONS:
        top = (
            projections[
                projections["position"]
                == position
            ]
            .sort_values(
                "projected_position_rank"
            )
            .head(10)
        )

        print()
        print(position)

        print(
            top[
                [
                    "projected_position_rank",
                    "player_name",
                    "projected_ppr",
                    "model_score",
                ]
            ].to_string(
                index=False
            )
        )

    print()
    print("Learned Model F coefficients:")
    print(
        coefficients.to_string(
            index=False
        )
    )


if __name__ == "__main__":
    main()
