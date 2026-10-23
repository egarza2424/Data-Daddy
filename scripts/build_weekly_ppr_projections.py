from pathlib import Path
import re
import json

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

    weeks = []

    if "snapshot_week" in snapshot.columns:
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

    if len(weeks) == 1:
        week = weeks[0]

        print(
            "Using NFL week from live "
            f"snapshot column: {week}"
        )

        return LIVE_SNAPSHOT_PATH, week

    print(
        "Live snapshot does not contain one "
        "usable snapshot_week value."
    )

    frozen_snapshots = list(
        Path("model-snapshots").glob(
            "2026-week*-pregame-model-snapshot.csv"
        )
    )

    if not frozen_snapshots:
        raise RuntimeError(
            "Could not determine target NFL week: "
            "live snapshot has no usable "
            "snapshot_week and no frozen "
            "week-numbered snapshot exists."
        )

    def frozen_week(path):
        match = re.search(
            r"2026-week(\d+)-pregame-model-snapshot\.csv$",
            path.name,
        )

        if not match:
            return -1

        return int(match.group(1))

    latest_frozen = max(
        frozen_snapshots,
        key=frozen_week,
    )

    week = frozen_week(
        latest_frozen
    )

    if week <= 0:
        raise RuntimeError(
            "Could not determine NFL week from "
            f"{latest_frozen.name}"
        )

    print(
        "Using NFL week from latest frozen "
        f"snapshot filename: {week}"
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

    # Exclude players whose teams do not have a game
    # in the target week. Bye-week players can remain
    # in the live player snapshot, but they must not
    # receive weekly fantasy projections.
    opponent = (
        snapshot["opponent"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    bye_week_mask = opponent.isin(
        [
            "",
            "NAN",
            "NONE",
            "NULL",
            "UNKNOWN",
            "BYE",
            "TBD",
        ]
    )

    bye_week_players = snapshot.loc[
        bye_week_mask,
        [
            "player_name",
            "position",
            "team",
        ],
    ].copy()

    if not bye_week_players.empty:
        print(
            "Excluding players without a "
            "target-week opponent:"
        )

        print(
            bye_week_players.to_string(
                index=False
            )
        )

    # A missing matchup feed is not a confirmed bye. Retain the
    # established Week 7 editorial WR while matchup data catches up.
    editorial_wr_feed_gap = (
        snapshot["snapshot_week"].eq(7)
        & snapshot["player_name"].eq("Luther Burden III")
        & snapshot["position"].eq("WR")
        & snapshot["team"].eq("CHI")
    )
    if (bye_week_mask & editorial_wr_feed_gap).any():
        print("Week 7: retaining Luther Burden III despite missing opponent feed.")
    snapshot = snapshot.loc[
        ~(bye_week_mask & ~editorial_wr_feed_gap)
    ].copy()
    # Exclude confirmed unavailable players when
    # roster status is present in the snapshot.
    # Older snapshots remain supported.
    unavailable_statuses = {
        "OUT",
        "IR",
        "INJURED_RESERVE",
        "INACTIVE",
        "SUSPENDED",
        "PUP",
        "EXEMPT",
        "EXEMPT_LIST",
        "RESERVE/EXEMPT",
        "RESERVE_EXEMPT",
    }

    unavailable_mask = pd.Series(
        False,
        index=snapshot.index,
    )

    for column in ("roster_status", "injury_status"):
        if column not in snapshot.columns:
            continue

        statuses = (
            snapshot[column]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.upper()
        )

        unavailable_mask |= statuses.isin(
            unavailable_statuses
        )

    # Confirmed Week 7 Colts absence: Warren is OUT; the
    # roster feed still labels him Questionable. Do not project him.
    unavailable_mask |= (
        snapshot["snapshot_week"].eq(7)
        & snapshot["player_name"].eq("Tyler Warren")
        & snapshot["position"].eq("TE")
        & snapshot["team"].eq("IND")
    )

    unavailable_players = snapshot.loc[
        unavailable_mask,
        [
            "player_name",
            "position",
            "team",
        ],
    ].copy()

    if not unavailable_players.empty:
        print(
            "Excluding confirmed unavailable players:"
        )
        print(
            unavailable_players.to_string(
                index=False
            )
        )

    snapshot = snapshot.loc[
        ~unavailable_mask
    ].copy()

    # Confirmed Week 7 NYG QB change (Oct 21, 2026):
    # J.J. McCarthy starts against Houston; Winston is the backup.
    # Do not project Winston as a starter or transfer his projection
    # to McCarthy. McCarthy must enter through the regular snapshot.
    if int(snapshot["snapshot_week"].iloc[0]) == 7:
        nyg_winston = (
            snapshot["position"].astype(str).str.upper().eq("QB")
            & snapshot["team"].astype(str).str.upper().eq("NYG")
            & snapshot["player_name"].astype(str).str.casefold().eq("jameis winston")
        )
        if nyg_winston.any():
            print("Week 7 starter update: excluding NYG backup Jameis Winston from PPR projections.")
            snapshot = snapshot.loc[~nyg_winston].copy()

    
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

        # Pregame review: identify generic feature profiles.
    # This is diagnostic only. Do not remove players
    # or modify their projected PPR values.
    core_columns = [
        "opportunity_score",
        "production_score",
        "usage_score",
        "redzone_score",
        "model_confidence_score",
    ]

    generic_profile = {
        "opportunity_score": 50.0,
        "production_score": 0.0,
        "usage_score": 20.0,
        "redzone_score": 50.0,
        "model_confidence_score": 50.0,
    }

    numeric_core = snapshot[core_columns].apply(
        pd.to_numeric,
        errors="coerce",
    )

    review_mask = snapshot["position"].isin(
        ["RB", "WR"]
    )

    for column, expected in generic_profile.items():
        review_mask &= numeric_core[column].eq(expected)

    review_players = snapshot.loc[
        review_mask,
        [
            "player_name",
            "position",
            "team",
            "opponent",
        ],
    ].copy()

    print(
        "Pregame low-information review: "
        f"{len(review_players)} players flagged."
    )

    if not review_players.empty:
        print(
            review_players.to_string(
                index=False
            )
        )
    # Remove TE rows whose entire opportunity/production profile is
    # the known missing-data fallback, not observed receiving evidence.
    # This does not exclude TEs with any measured usage or production.
    te_fallback = snapshot["position"].eq("TE")
    for column, value in {
        "opportunity_score": 50,
        "production_score": 0,
        "usage_score": 20,
        "redzone_score": 50,
        "model_confidence_score": 50,
    }.items():
        te_fallback &= pd.to_numeric(
            snapshot[column], errors="coerce"
        ).eq(value)

    excluded_te = snapshot.loc[
        te_fallback, ["player_name", "team"]
    ]
    if not excluded_te.empty:
        print(
            "Excluding TE missing-evidence fallback projections:"
        )
        print(excluded_te.to_string(index=False))
    snapshot = snapshot.loc[~te_fallback].copy()

    # Diagnostic: detect duplicate player identities.
    # Preserve all rows until identity is verified.
    normalized_names = (
        snapshot["player_name"]
        .astype(str)
        .str.lower()
        .str.replace(
            r"\s+(jr\.?|sr\.?|ii|iii|iv)$",
            "",
            regex=True,
        )
        .str.replace(
            r"[^a-z0-9]",
            "",
            regex=True,
        )
    )

    identity_key = (
        normalized_names
        + "|"
        + snapshot["team"].astype(str).str.upper()
    )

    duplicate_mask = identity_key.duplicated(
        keep=False
    )

    duplicates = snapshot.loc[
        duplicate_mask,
        ["player_id", "player_name", "position", "team"],
    ]

    print(
        "Pregame identity review: "
        f"{len(duplicates)} rows flagged."
    )

    if not duplicates.empty:
        print(
            duplicates.to_string(index=False)
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
    )

    if missing_current.any().any():
        affected_players = (
            current.loc[
                missing_current.any(axis=1),
                "player_name",
            ]
            .astype(str)
            .tolist()
        )

        missing_counts = (
            missing_current
            .sum()
        )

        print(
            f"{position}: neutralizing missing "
            "live features to 50."
        )

        print(
            "Affected players: "
            + ", ".join(
                affected_players[:20]
            )
        )

        print(
            "Missing feature counts:"
        )

        print(
            missing_counts[
                missing_counts > 0
            ].to_string()
        )

        current[features] = (
            current[features]
            .fillna(50.0)
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

    snapshot["snapshot_week"] = target_week

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
    # Historical held-out TE challenger: prior-week-only 50% PPG blend.
    # The existing snapshot availability and missing-evidence filters run first.
    if target_week == 7:
        from audit_te_ppg_challenger import build_challenger

        stats_path = Path("nfl-stats.json")
        if not stats_path.exists():
            raise RuntimeError("TE blend requires nfl-stats.json")
        with stats_path.open(encoding="utf-8") as handle:
            stats = json.load(handle)
        te_audit = build_challenger(projections, stats, target_week, 0.5)
        te_mask = projections["position"].eq("TE")
        matched = projections.loc[te_mask, ["player_name", "team"]].merge(
            te_audit[["player_name", "team", "challenger_ppr", "prior_games"]],
            on=["player_name", "team"], how="left", validate="one_to_one"
        )
        if matched["challenger_ppr"].isna().any():
            raise RuntimeError("Missing TE challenger identity match")
        te_indices = projections.index[te_mask]
        projections.loc[te_indices, "projected_ppr"] = matched["challenger_ppr"].to_numpy()
        blended = matched["prior_games"].to_numpy() >= 2
        projections.loc[te_indices[blended], "projection_model"] = "F_TE_50pct_prior_PPG"
        projections.loc[te_indices, "projected_position_rank"] = (
            projections.loc[te_indices, "projected_ppr"]
            .rank(method="min", ascending=False).astype(int)
        )
        print(f"Week 7 TE PPG blend applied to {blended.sum()} players.")
        print("Role-change and injury verification still required before social publishing.")
    # Week 7 WR PPR challenger: 50% prior-game PPG, validated on
    # held-out 2025 WRs for MAE. Keep AI position_rank unchanged:
    # the blend did not improve historical Top-24 recall.
    if target_week == 7:
        import re

        def wr_key(name, team):
            name = re.sub(
                r"\\s+(jr\\.?|sr\\.?|ii|iii|iv)$",
                "",
                str(name).lower().strip(),
            )
            return (
                re.sub(r"[^a-z0-9]", "", name)
                + "|"
                + str(team).upper()
            )

        weekly = pd.DataFrame(stats["players"])
        required = {
            "season", "week", "position", "team",
            "player_display_name", "receptions",
            "receiving_yards", "receiving_tds",
            "rushing_yards", "rushing_tds",
        }
        if required - set(weekly.columns):
            raise RuntimeError("WR PPG blend missing weekly stat columns")
        season_type = weekly.get(
            "season_type", pd.Series("REG", index=weekly.index)
        )
        weekly = weekly.loc[
            weekly["position"].eq("WR")
            & season_type.eq("REG")
            & pd.to_numeric(weekly["season"], errors="coerce").eq(2026)
            & pd.to_numeric(weekly["week"], errors="coerce").lt(target_week)
        ].copy()
        for col in [
            "receptions", "receiving_yards", "receiving_tds",
            "rushing_yards", "rushing_tds",
        ]:
            weekly[col] = pd.to_numeric(
                weekly[col], errors="coerce"
            ).fillna(0)
        weekly["ppr"] = (
            weekly["receptions"]
            + weekly["receiving_yards"] / 10
            + 6 * weekly["receiving_tds"]
            + weekly["rushing_yards"] / 10
            + 6 * weekly["rushing_tds"]
        )
        weekly["key"] = [
            wr_key(n, t)
            for n, t in zip(
                weekly["player_display_name"], weekly["team"]
            )
        ]
        if weekly.duplicated(["key", "week"]).any():
            raise RuntimeError("Duplicate WR identity-week in PPG history")
        prior = weekly.groupby("key")["ppr"].agg(["count", "mean"])
        wr_mask = projections["position"].eq("WR")
        wr_indices = projections.index[wr_mask]
        wr_keys = [
            wr_key(n, t)
            for n, t in zip(
                projections.loc[wr_mask, "player_name"],
                projections.loc[wr_mask, "team"],
            )
        ]
        games = pd.Series(wr_keys).map(prior["count"]).fillna(0)
        ppg = pd.Series(wr_keys).map(prior["mean"])
        eligible = games.ge(2) & ppg.notna()
        values = projections.loc[wr_indices, "projected_ppr"].to_numpy(
            dtype=float, copy=True
        )
        mask = eligible.to_numpy()
        values[mask] = (
            0.5 * values[mask]
            + 0.5 * ppg.to_numpy(dtype=float)[mask]
        )
        projections.loc[wr_indices, "projected_ppr"] = values
        projections.loc[
            wr_indices[mask], "projection_model"
        ] = "F_WR_50pct_prior_PPG"
        projections.loc[wr_indices, "projected_position_rank"] = (
            projections.loc[wr_indices, "projected_ppr"]
            .rank(method="min", ascending=False)
            .astype(int)
        )
        print(
            f"Week 7 WR 50% PPG blend applied to {mask.sum()} players; "
            "AI score ranks unchanged."
        )
        print(
            "WR PPR blend improves historical MAE but not Top-24 recall; "
            "injury and role verification required before publication."
        )
    # Apply experimental J2 to RBs only.
    # All other positions and unmatched RBs retain Model F.
    j2_path = (
        OUTPUT_DIR
        / "validation"
        / f"2026-week{target_week}-rb-j2-experimental.csv"
    )

    if j2_path.exists():
        j2 = pd.read_csv(j2_path)

        required = {
            "player_name",
            "team",
            "snapshot_week",
            "j2_projection_status",
            "j2_projected_ppr",
        }

        if required - set(j2.columns):
            raise RuntimeError("J2 export missing required columns")

        weeks = set(
            pd.to_numeric(
                j2["snapshot_week"],
                errors="coerce",
            ).dropna().astype(int)
        )

        if weeks != {target_week}:
            raise RuntimeError("J2 snapshot week mismatch")

        eligible = j2.loc[
            j2["j2_projection_status"].eq(
                "experimental_2026_features"
            )
        ].copy()

        if eligible.duplicated(["player_name", "team"]).any():
            raise RuntimeError("Duplicate J2 player identities")

        eligible["j2_projected_ppr"] = pd.to_numeric(
            eligible["j2_projected_ppr"],
            errors="coerce",
        )

        eligible = eligible.dropna(
            subset=["j2_projected_ppr"]
        )

        if (eligible["j2_projected_ppr"] < 0).any():
            raise RuntimeError("Negative J2 projection")

        rb_mask = projections["position"].eq("RB")

        matched = projections.loc[
            rb_mask,
            ["player_name", "team"],
        ].merge(
            eligible[
                ["player_name", "team", "j2_projected_ppr"]
            ],
            on=["player_name", "team"],
            how="left",
            validate="one_to_one",
        )

        values = matched["j2_projected_ppr"].to_numpy()
        rb_indices = projections.index[rb_mask]
        use_j2 = np.isfinite(values)

        projections.loc[
            rb_indices[use_j2],
            "projected_ppr",
        ] = values[use_j2]

        projections.loc[
            rb_indices[use_j2],
            "projection_model",
        ] = "J2_RB_role_stability"

        projections.loc[
            rb_indices,
            "projected_position_rank",
        ] = (
            projections.loc[
                rb_indices,
                "projected_ppr",
            ]
            .rank(method="min", ascending=False)
            .astype(int)
        )

        print(
            f"J2 applied to {use_j2.sum()} RBs; "
            f"Model F retained for {(~use_j2).sum()} RBs."
        )
    # Week 7 only: provisional Josh Jacobs return.
    # Manual estimate, not a J2 prediction.
    if target_week == 7:
        jacobs_mask = (
            projections["position"].eq("RB")
            & projections["player_name"].eq("Josh Jacobs")
            & projections["team"].eq("GB")
        )

        if jacobs_mask.sum() != 1:
            raise RuntimeError(
                "Expected exactly one eligible Josh Jacobs "
                "row for Week 7. Check availability and identity."
            )

        projections.loc[
            jacobs_mask, "projected_ppr"
        ] = 13.00

        projections.loc[
            jacobs_mask, "projection_model"
        ] = "Manual_Week7_RB_override"
        # Week 7 only: provisional backup role for Pierre Strong.
        strong_mask = (
            projections["position"].eq("RB")
            & projections["player_name"].isin(
                ["Pierre Strong", "Pierre Strong Jr."]
            )
            & projections["team"].eq("GB")
        )

        # Pierre Strong may be absent from a refreshed roster
        # snapshot. Do not fail every position's projection run
        # when a provisional backup is no longer eligible.
        strong_count = int(strong_mask.sum())
        if strong_count > 1:
            raise RuntimeError(
                "Duplicate Pierre Strong RB rows for Week 7."
            )
        if strong_count == 1:
            projections.loc[
                strong_mask, "projected_ppr"
            ] = 6.00
            projections.loc[
                strong_mask, "projection_model"
            ] = "Manual_Week7_RB_override"
        else:
            print(
                "Pierre Strong absent from current Week 7 "
                "snapshot; skipping provisional RB override."
            )
        
        # Recalculate RB ranks using final projections.
        rb_mask = projections["position"].eq("RB")

        projections.loc[
            rb_mask, "projected_position_rank"
        ] = (
            projections.loc[rb_mask, "projected_ppr"]
            .rank(method="min", ascending=False)
            .astype(int)
        )

        print(
            "Week 7 provisional override: "
            "Josh Jacobs = 13.00 PPR."
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

    # Preserve availability metadata in the output.
    # Old snapshots may not contain these columns.
    for column, default in {
        "roster_status": "UNKNOWN",
        "injury_status": "",
    }.items():
        if column not in projections.columns:
            projections[column] = default

        projections[column] = (
            projections[column]
            .fillna(default)
            .astype(str)
            .str.strip()
        )

    # Week 7 WR editorial PPR board (human-adjusted; not Model F).
    # This board is intentionally distinct from position_rank/model_score.
    if target_week == 7:
        wr_editorial = [
            ("Puka Nacua", 22.1),
            ("Jaxon Smith-Njigba", 21.1),
            ("Amon-Ra St. Brown", 20.1),
            ("Ja'Marr Chase", 19.2),
            ("CeeDee Lamb", 18.8),
            ("Drake London", 18.2),
            ("Tetairoa McMillan", 17.2),
            ("Malik Nabers", 17.1),
            ("Justin Jefferson", 16.8),
            ("Nico Collins", 16.7),
            ("Christian Watson", 16.2),
            ("Matthew Golden", 15.6),
            ("Zay Flowers", 15.5),
            ("Chris Olave", 15.4),
            ("George Pickens", 14.9),
            ("Jalen Coker", 14.6),
            ("DeVonta Smith", 13.9),
            ("Garrett Wilson", 13.8),
            ("Tee Higgins", 13.7),
            ("Germie Bernard", 13.4),
            ("Emeka Egbuka", 12.8),
            ("Luther Burden III", 12.5),
            ("Malik Washington", 12.1),
            ("Carnell Tate", 11.9),
        ]
        wr_mask = projections["position"].eq("WR")
        evans = wr_mask & projections["player_name"].eq("Mike Evans")
        projections = projections.loc[~evans].copy()
        wr_mask = projections["position"].eq("WR")
        chosen = []
        for name, ppr in wr_editorial:
            matches = projections.index[
                wr_mask & projections["player_name"].eq(name)
            ]
            if len(matches) != 1:
                raise RuntimeError(
                    f"Week 7 editorial WR missing/duplicate: {name} ({len(matches)})"
                )
            idx = matches[0]
            chosen.append(idx)
            projections.loc[idx, "projected_ppr"] = ppr
            projections.loc[idx, "projection_model"] = (
                "Editorial_Week7_WR_team_total_adjusted"
            )
        # Keep all remaining WRs below the curated Top 24 without
        # altering their underlying PPR estimates or AI rankings.
        others = projections.loc[
            wr_mask & ~projections.index.isin(chosen)
        ].sort_values(
            ["projected_ppr", "player_name"],
            ascending=[False, True],
        ).index.tolist()
        for rank, idx in enumerate(chosen + others, start=1):
            projections.loc[idx, "projected_position_rank"] = rank
        print("Week 7 editorial WR Top 24 applied; Mike Evans excluded.")

    # Starter-absence opportunity challenger: use observed target volume
    # while the starter was unavailable, shrink a one-game sample toward
    # a conservative replacement-role prior, and retain model efficiency.
    # Week 7 Colts: Mallory drew six targets with Warren absent in Week 6.
    if target_week == 7:
        mallory = (
            projections["position"].eq("TE")
            & projections["team"].eq("IND")
            & projections["player_name"].eq("Will Mallory")
        )
        if mallory.sum() == 1:
            idx = projections.index[mallory][0]
            baseline = float(projections.at[idx, "projected_ppr"])
            observed_targets, prior_targets, prior_games = 6.0, 3.0, 2.0
            expected_targets = (
                observed_targets + prior_games * prior_targets
            ) / (1.0 + prior_games)
            # Conservative PPR per target until routes/efficiency samples
            # justify a stronger assumption. Not a guaranteed target share.
            challenger = round(expected_targets * 1.35, 2)
            adjusted = round(max(baseline, challenger), 2)
            projections.at[idx, "projected_ppr"] = adjusted
            projections.at[idx, "projection_model"] = (
                "StarterAbsence_TE_target_shrinkage_Week7"
            )
            print(
                f"Mallory Warren-out role challenger: "
                f"{baseline:.2f} -> {adjusted:.2f} PPR "
                f"({expected_targets:.1f} expected targets)."
            )
            te_mask = projections["position"].eq("TE")
            te_order = projections.loc[te_mask].sort_values(
                ["projected_ppr", "player_name"],
                ascending=[False, True],
            ).index
            projections.loc[te_order, "projected_position_rank"] = (
                list(range(1, len(te_order) + 1))
            )

    # Week 7 TE editorial placements, distinct from the validated TE model.
    # Preserve Model F AI scores; adjust only weekly PPR and PPR ranks.
    if target_week == 7:
        te_mask = projections["position"].eq("TE")
        te_order = projections.loc[te_mask].sort_values(
            ["projected_ppr", "player_name"], ascending=[False, True]
        ).index.tolist()
        moves = [
            ("Mark Andrews", 15, 9.40),
            ("Michael Mayer", 17, 9.20),
            ("Juwan Johnson", 18, 9.12),
        ]
        selected = {}
        for name, rank, ppr in moves:
            matches = projections.index[
                te_mask & projections["player_name"].eq(name)
            ]
            if len(matches) != 1:
                raise RuntimeError(
                    f"Week 7 TE editorial player missing/duplicate: {name}"
                )
            selected[name] = matches[0]
        te_order = [idx for idx in te_order if idx not in selected.values()]
        for name, rank, ppr in sorted(moves, key=lambda x: x[1]):
            idx = selected[name]
            te_order.insert(rank - 1, idx)
            projections.loc[idx, "projected_ppr"] = ppr
            projections.loc[idx, "projection_model"] = (
                "Editorial_Week7_TE_role_matchup_adjusted"
            )
        for rank, idx in enumerate(te_order, start=1):
            projections.loc[idx, "projected_position_rank"] = rank
        print("Week 7 TE editorial placements: Andrews 15, Mayer 17, Johnson 18.")

    # Week 7 editorial AI ranking placement for Emanuel Wilson.
    # Keep his model_score intact; only the displayed rank changes.
    # The website independently applies the same placement after Pierce.
    if target_week == 7:
        rb_sorted = projections.loc[
            projections["position"].eq("RB")
        ].sort_values(["position_rank", "player_name"])
        wilson = rb_sorted.loc[
            rb_sorted["player_name"].eq("Emanuel Wilson")
            & rb_sorted["team"].eq("SEA")
        ]
        pierce = rb_sorted.loc[
            rb_sorted["player_name"].eq("Dameon Pierce")
        ]
        if len(wilson) != 1 or len(pierce) != 1:
            raise RuntimeError("Missing Wilson or Pierce for Week 7 RB editorial placement.")
        wilson_index = wilson.index[0]
        order = [idx for idx in rb_sorted.index if idx != wilson_index]
        pierce_index = pierce.index[0]
        order.insert(order.index(pierce_index) + 1, wilson_index)
        for rank, idx in enumerate(order, start=1):
            projections.loc[idx, "position_rank"] = rank

    # Apply optional week-scoped analyst deltas after baseline and editorial logic.
    # Keep original model values in separate columns for accuracy comparisons.
    from analyst_adjustments import apply_adjustments

    projections, analyst_audit = apply_adjustments(
        projections, season=2026, week=target_week
    )
    if not analyst_audit.empty:
        audit_dir = Path("projection-model/validation")
        audit_dir.mkdir(parents=True, exist_ok=True)
        audit_path = audit_dir / f"2026-week{target_week}-analyst-adjustments-audit.csv"
        analyst_audit.to_csv(audit_path, index=False)
        print(f"Applied {len(analyst_audit)} analyst adjustments; audit: {audit_path}")

    output_columns = [
        "snapshot_week",
        "player_id",
        "player_name",
        "position",
        "team",
        "opponent",
        "roster_status",
        "injury_status",
        "model_score",
        "original_model_score",
        "position_rank",
        "projected_ppr",
        "original_projected_ppr",
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
    print()
    print("Projection availability audit:")

    print(
        "Available/unknown players projected: "
        f"{len(projections)}"
    )

    print(
        "Roster status breakdown:"
    )

    print(
        projections["roster_status"]
        .value_counts(dropna=False)
        .to_string()
    )

    print(
        "Injury status breakdown:"
    )

    print(
        projections["injury_status"]
        .replace("", "NOT_REPORTED")
        .value_counts(dropna=False)
        .to_string()
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
