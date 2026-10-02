"""
Build leakage-safe historical player-week data for the
Fantasy AI Player Lab PPR projection model.

Phase 1 builds the core historical signals that can be
reconstructed directly from nflverse weekly player data:

- Recent Production
- Opportunity
- Usage
- Red-Zone Usage
- Model Confidence
- Actual PPR target

IMPORTANT:
For target week W, every feature is calculated using only
games from weeks < W.

Later phases will join:
- defensive matchup
- play-caller matchup
- player vs defensive play caller
- trench matchup
- scoring environment
- historical availability/risk
"""

import argparse
import csv
import gzip
import io
from pathlib import Path

import numpy as np
import pandas as pd


POSITIONS = {"QB", "RB", "WR", "TE"}


def numeric(series):
    return pd.to_numeric(
        series,
        errors="coerce"
    ).fillna(0.0)


def ensure_column(df, column):
    if column not in df.columns:
        df[column] = 0.0


def ppr_points(df):
    """
    Full-PPR scoring matching the Fantasy AI Player Lab
    validation workflow.
    """

    required = [
        "passing_yards",
        "passing_tds",
        "interceptions",
        "rushing_yards",
        "rushing_tds",
        "receptions",
        "receiving_yards",
        "receiving_tds",
    ]

    for column in required:
        ensure_column(df, column)

    return (
        numeric(df["passing_yards"]) / 25.0
        + numeric(df["passing_tds"]) * 4.0
        - numeric(df["interceptions"]) * 2.0
        + numeric(df["rushing_yards"]) / 10.0
        + numeric(df["rushing_tds"]) * 6.0
        + numeric(df["receptions"])
        + numeric(df["receiving_yards"]) / 10.0
        + numeric(df["receiving_tds"]) * 6.0
    )


def opportunity_value(row):
    position = row["position"]

    carries = float(row.get("carries", 0) or 0)
    targets = float(row.get("targets", 0) or 0)

    attempts = float(
        row.get(
            "attempts",
            row.get("passing_attempts", 0)
        ) or 0
    )

    if position == "QB":
        return attempts + carries

    if position == "RB":
        return carries + targets

    return targets + carries


def stability_score(values):
    values = [
        float(value)
        for value in values
        if pd.notna(value)
    ]

    if len(values) < 2:
        return 50.0

    average = np.mean(values)

    if average <= 0:
        return 50.0

    std = np.std(values)

    coefficient_of_variation = (
        std / average
    )

    score = (
        100.0
        - coefficient_of_variation * 100.0
    )

    return float(
        np.clip(
            round(score),
            20,
            100
        )
    )


def prepare_stats(stats):
    stats = stats.copy()

    aliases = {
        "player_display_name": [
            "player_display_name",
            "player_name",
        ],
        "team": [
            "team",
            "recent_team",
        ],
        "attempts": [
            "attempts",
            "passing_attempts",
        ],
        "carries": [
            "carries",
            "rushing_attempts",
        ],
    }
    for target, choices in aliases.items():
        if target in stats.columns:
            continue

        for choice in choices:
            if choice in stats.columns:
                stats[target] = stats[choice]
                break

    required = [
        "season",
        "week",
        "player_id",
        "player_display_name",
        "position",
        "team",
    ]

    missing = [
        column
        for column in required
        if column not in stats.columns
    ]

    if missing:
        raise ValueError(
            f"Weekly stats missing columns: {missing}"
        )

    optional_numeric = [
        "attempts",
        "passing_attempts",
        "passing_yards",
        "passing_tds",
        "interceptions",
        "carries",
        "rushing_attempts",
        "rushing_yards",
        "rushing_tds",
        "targets",
        "receptions",
        "receiving_yards",
        "receiving_tds",
        "red_zone_pass_attempts",
        "red_zone_carries",
        "red_zone_targets",
    ]

    for column in optional_numeric:
        ensure_column(stats, column)
        stats[column] = numeric(stats[column])

    stats["season"] = pd.to_numeric(
        stats["season"],
        errors="coerce"
    )

    stats["week"] = pd.to_numeric(
        stats["week"],
        errors="coerce"
    )

    stats = stats[
        stats["position"].isin(POSITIONS)
    ].copy()

    if "season_type" in stats.columns:
        stats = stats[
            stats["season_type"].eq("REG")
        ].copy()

    stats["actual_ppr"] = ppr_points(stats)

    stats["opportunity_raw"] = stats.apply(
        opportunity_value,
        axis=1
    )

    return stats


def load_red_zone_pbp(
    pbp_path,
    season,
):
    """
    Build player-week red-zone usage from nflverse
    play-by-play.

    Red zone = offense at opponent 20-yard line or closer.
    """

    pbp_path = Path(pbp_path)

    if not pbp_path.exists():
        raise FileNotFoundError(
            f"Play-by-play file not found: {pbp_path}"
        )

    opener = (
        gzip.open
        if pbp_path.suffix.lower() == ".gz"
        else open
    )

    red_zone_stats = {}

    with opener(
        pbp_path,
        "rt",
        encoding="utf-8",
        newline="",
    ) as handle:
        reader = csv.DictReader(handle)

        for play in reader:
            if play.get("season_type") != "REG":
                continue

            try:
                play_season = int(
                    float(
                        play.get("season")
                        or season
                    )
                )
            except (TypeError, ValueError):
                continue

            if play_season != season:
                continue

            try:
                yardline = float(
                    play.get("yardline_100")
                    or 999
                )
            except (TypeError, ValueError):
                continue

            if yardline > 20:
                continue

            try:
                week = int(
                    float(
                        play.get("week")
                        or 0
                    )
                )
            except (TypeError, ValueError):
                continue

            if week <= 0:
                continue

            passer_id = play.get(
                "passer_player_id"
            )

            rusher_id = play.get(
                "rusher_player_id"
            )

            receiver_id = play.get(
                "receiver_player_id"
            )

            pass_attempt = (
                play.get("pass_attempt") == "1"
            )

            rush_attempt = (
                play.get("rush_attempt") == "1"
            )

            def get_record(player_id):
                key = (
                    str(player_id),
                    week,
                )

                if key not in red_zone_stats:
                    red_zone_stats[key] = {
                        "red_zone_pass_attempts": 0,
                        "red_zone_carries": 0,
                        "red_zone_targets": 0,
                    }

                return red_zone_stats[key]

            if pass_attempt and passer_id:
                get_record(passer_id)[
                    "red_zone_pass_attempts"
                ] += 1

            if rush_attempt and rusher_id:
                get_record(rusher_id)[
                    "red_zone_carries"
                ] += 1

            if pass_attempt and receiver_id:
                get_record(receiver_id)[
                    "red_zone_targets"
                ] += 1

    print(
        "Built red-zone play-by-play records "
        f"for {len(red_zone_stats)} "
        "player-week combinations."
    )

    return red_zone_stats


def attach_red_zone_stats(
    stats,
    red_zone_stats,
):
    """
    Attach player-week red-zone PBP counts to the
    nflverse weekly player-stat rows.
    """

    stats = stats.copy()

    for column in [
        "red_zone_pass_attempts",
        "red_zone_carries",
        "red_zone_targets",
    ]:
        stats[column] = 0.0

    matched = 0

    for index, row in stats.iterrows():
        try:
            week = int(row["week"])
        except (TypeError, ValueError):
            continue

        key = (
            str(row["player_id"]),
            week,
        )

        values = red_zone_stats.get(key)

        if values is None:
            continue

        matched += 1

        for column, value in values.items():
            stats.at[
                index,
                column
            ] = float(value)

    print(
        "Matched red-zone play-by-play to "
        f"{matched} weekly player-stat rows."
    )

    return stats


def recent_player_games(
    history,
    player_id,
    target_week,
    limit=3,
):
    rows = history[
        (history["player_id"] == player_id)
        & (history["week"] < target_week)
    ].copy()

    return (
        rows
        .sort_values("week", ascending=False)
        .head(limit)
    )


def team_game_rows(
    history,
    team,
    week,
):
    return history[
        (history["team"] == team)
        & (history["week"] == week)
    ]


def usage_value(
    player_row,
    team_rows,
):
    position = player_row["position"]

    carries = float(
        player_row.get("carries", 0) or 0
    )

    targets = float(
        player_row.get("targets", 0) or 0
    )

    team_carries = numeric(
        team_rows["carries"]
    ).sum()

    if position == "QB":
        if team_carries <= 0:
            return 0.0

        return carries / team_carries

    team_targets = numeric(
        team_rows["targets"]
    ).sum()

    carry_share = (
        carries / team_carries
        if team_carries > 0
        else 0.0
    )

    target_share = (
        targets / team_targets
        if team_targets > 0
        else 0.0
    )

    return carry_share + target_share
return carry_share + target_share

def redzone_raw(row):
    position = row["position"]

    if position == "QB":
        return (
            float(
                row.get(
                    "red_zone_pass_attempts",
                    0
                ) or 0
            )
            + float(
                row.get(
                    "red_zone_carries",
                    0
                ) or 0
            )
        )

    if position == "RB":
        return float(
            row.get(
                "red_zone_carries",
                0
            ) or 0
        )

    return float(
        row.get(
            "red_zone_targets",
            0
        ) or 0
    )


def build_week(
    season_stats,
    target_week,
):
    history = season_stats[
        season_stats["week"] < target_week
    ].copy()

    current = season_stats[
        season_stats["week"] == target_week
    ].copy()

    if history.empty or current.empty:
        return pd.DataFrame()

    rows = []

    recent_cache = {}

    for player in current.itertuples(index=False):
        player_dict = player._asdict()

        player_id = player_dict["player_id"]
        position = player_dict["position"]

        recent = recent_player_games(
            history,
            player_id,
            target_week,
        )

        if recent.empty:
            continue

        recent_cache[player_id] = recent

        production_raw = float(
            recent["actual_ppr"].mean()
        )

        opportunity_raw = float(
            recent["opportunity_raw"].mean()
        )

        usage_values = []
        confidence_usage_values = []

        for game in recent.itertuples(index=False):
            game_dict = game._asdict()

            team_rows = team_game_rows(
                history,
                game_dict["team"],
                game_dict["week"],
            )

            usage_values.append(
                usage_value(
                    game_dict,
                    team_rows,
                )
            )

            confidence_usage_values.append(
                confidence_usage_value(
                    game_dict,
                    team_rows,
                )
            )

        usage_raw = (
            float(np.mean(usage_values))
            if usage_values
            else 0.0
        )

        redzone_values = [
            redzone_raw(game._asdict())
            for game in recent.itertuples(
                index=False
            )
        ]

        redzone_per_game = float(
            np.mean(redzone_values)
        )

        fantasy_values = (
            recent["actual_ppr"]
            .astype(float)
            .tolist()
        )

        opportunity_values = (
            recent["opportunity_raw"]
            .astype(float)
            .tolist()
        )

        production_consistency = (
            stability_score(fantasy_values)
        )

        opportunity_stability = (
            stability_score(
                opportunity_values
            )
        )

        usage_stability = (
            stability_score(
                confidence_usage_values
            )
        )
        # Historical injury/availability information
        # is not yet joined in Phase 1.
        availability = 95.0

        confidence_score = (
            production_consistency * 0.35
            + opportunity_stability * 0.30
            + usage_stability * 0.20
            + availability * 0.15
        )

        rows.append(
            {
                "season":
                    int(player_dict["season"]),

                "week":
                    int(target_week),

                "player_id":
                    player_id,

                "player_name":
                    player_dict[
                        "player_display_name"
                    ],

                "position":
                    position,

                "team":
                    player_dict["team"],

                "production_raw":
                    production_raw,

                "opportunity_raw":
                    opportunity_raw,

                "usage_raw":
                    usage_raw,

                "redzone_raw":
                    redzone_per_game,

                "production_consistency":
                    production_consistency,

                "opportunity_stability":
                    opportunity_stability,

                "usage_stability":
                    usage_stability,

                "model_confidence_score":
                    round(
                        confidence_score,
                        1
                    ),

                "actual_ppr":
                    round(
                        float(
                            player_dict[
                                "actual_ppr"
                            ]
                        ),
                        2
                    ),
            }
        )

    week_df = pd.DataFrame(rows)

    if week_df.empty:
        return week_df

    # ---------------------------------------------
    # NORMALIZE PRODUCTION AND OPPORTUNITY
    # EXACTLY WITHIN POSITION / TARGET WEEK
    # ---------------------------------------------

    for position in POSITIONS:
        mask = (
            week_df["position"] == position
        )

        position_rows = week_df.loc[mask]

        if position_rows.empty:
            continue

        production_high = (
            position_rows[
                "production_raw"
            ].max()
        )

        opportunity_high = (
            position_rows[
                "opportunity_raw"
            ].max()
        )

        if production_high > 0:
            week_df.loc[
                mask,
                "production_score"
            ] = (
                position_rows[
                    "production_raw"
                ]
                / production_high
                * 100.0
            ).round()

        if opportunity_high > 0:
            week_df.loc[
                mask,
                "opportunity_score"
            ] = (
                position_rows[
                    "opportunity_raw"
                ]
                / opportunity_high
                * 100.0
            ).round()

    week_df["production_score"] = (
        week_df["production_score"]
        .fillna(50)
        .clip(0, 100)
    )

    week_df["opportunity_score"] = (
        week_df["opportunity_score"]
        .fillna(50)
        .clip(0, 100)
    )

    # Current live Usage formula.
    qb_mask = (
        week_df["position"] == "QB"
    )

    week_df["usage_score"] = (
        week_df["usage_raw"] * 100.0
    ).round()

    week_df.loc[
        qb_mask,
        "usage_score"
    ] = (
        week_df.loc[
            qb_mask,
            "usage_raw"
        ]
        * 400.0
    ).round()

    week_df["usage_score"] = (
        week_df["usage_score"]
        .clip(0, 100)
    )

    # Current live Red-Zone formula.
    rb_mask = (
        week_df["position"] == "RB"
    )

    receiver_mask = (
        week_df["position"].isin(
            ["WR", "TE"]
        )
    )

    qb_rows = week_df[qb_mask]

    if not qb_rows.empty:
        qb_high = qb_rows[
            "redzone_raw"
        ].max()

        if qb_high > 0:
            week_df.loc[
                qb_mask,
                "redzone_score"
            ] = (
                qb_rows["redzone_raw"]
                / qb_high
                * 100.0
            ).round()

    week_df.loc[
        rb_mask,
        "redzone_score"
    ] = (
        week_df.loc[
            rb_mask,
            "redzone_raw"
        ]
        / 4.0
        * 100.0
    ).round()

    week_df.loc[
        receiver_mask,
        "redzone_score"
    ] = (
        week_df.loc[
            receiver_mask,
            "redzone_raw"
        ]
        / 2.0
        * 100.0
    ).round()

    week_df["redzone_score"] = (
        week_df["redzone_score"]
        .fillna(50)
        .clip(0, 100)
    )

    return week_df


def build_dataset(
    stats,
    season,
    first_week,
    last_week,
):
    stats = prepare_stats(stats)

    season_stats = stats[
        stats["season"] == season
    ].copy()

    if season_stats.empty:
        raise RuntimeError(
            f"No stats found for season {season}"
        )

    outputs = []

    for week in range(
        first_week,
        last_week + 1,
    ):
        week_df = build_week(
            season_stats,
            week,
        )

        if week_df.empty:
            print(
                f"Week {week}: no eligible rows"
            )
            continue

        print(
            f"Week {week}: "
            f"{len(week_df)} player rows"
        )

        outputs.append(week_df)

    if not outputs:
        raise RuntimeError(
            "No historical player-week rows created."
        )

    result = pd.concat(
        outputs,
        ignore_index=True,
    )

    columns = [
        "season",
        "week",
        "player_id",
        "player_name",
        "position",
        "team",
        "opportunity_score",
        "production_score",
        "usage_score",
        "redzone_score",
        "model_confidence_score",
        "production_raw",
        "opportunity_raw",
        "usage_raw",
        "redzone_raw",
        "actual_ppr",
    ]

    return result[columns]


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--stats",
        required=True,
        help=(
            "nflverse weekly player stats "
            "CSV or parquet"
        ),
    )

    parser.add_argument(
        "--season",
        type=int,
        default=2025,
    )

    parser.add_argument(
        "--first-week",
        type=int,
        default=4,
    )

    parser.add_argument(
        "--last-week",
        type=int,
        default=18,
    )

    parser.add_argument(
        "--output",
        default=(
            "projection-model/"
            "2025-historical-ppr-dataset.csv"
        ),
    )

    args = parser.parse_args()

    path = Path(args.stats)

    if path.suffix.lower() == ".parquet":
        stats = pd.read_parquet(path)
    else:
        stats = pd.read_csv(path)

    red_zone_stats = load_red_zone_pbp(
        args.pbp,
        args.season,
    )

    stats = attach_red_zone_stats(
        stats,
        red_zone_stats,
    )

    result = build_dataset(
        stats,
        args.season,
        args.first_week,
        args.last_week,
    )
    output = Path(args.output)

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    result.to_csv(
        output,
        index=False,
    )

    print()
    print(
        f"Wrote {len(result)} historical "
        f"player-week rows to {output}"
    )

    print()
    print("Rows by position:")
    print(
        result.groupby("position")
        .size()
        .sort_index()
        .to_string()
    )

    print()
    print("Rows by week:")
    print(
        result.groupby("week")
        .size()
        .sort_index()
        .to_string()
    )


if __name__ == "__main__":
    main()
