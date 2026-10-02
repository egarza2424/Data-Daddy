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

def normalize_team(team):
    """
    Normalize team abbreviations to the aliases used
    throughout Fantasy AI Player Lab.
    """

    aliases = {
        "LAR": "LA",
        "JAX": "JAC",
        "WAS": "WSH",
    }

    team = str(team or "").strip().upper()

    return aliases.get(team, team)
def load_schedule(
    games_path,
    season,
):
    """
    Build the complete regular-season team/opponent
    schedule used by the historical Matchup signal.

    Unlike Scoring Environment, this does not require
    spread or total betting lines.
    """

    games_path = Path(games_path)

    if not games_path.exists():
        raise FileNotFoundError(
            "Games file not found: "
            f"{games_path}"
        )

    games = pd.read_csv(games_path)

    required = {
        "season",
        "week",
        "game_type",
        "home_team",
        "away_team",
    }

    missing = sorted(
        required - set(games.columns)
    )

    if missing:
        raise ValueError(
            "Games file missing schedule columns: "
            f"{missing}"
        )

    games["season"] = pd.to_numeric(
        games["season"],
        errors="coerce",
    )

    games["week"] = pd.to_numeric(
        games["week"],
        errors="coerce",
    )

    games = games[
        (games["season"] == season)
        & games["game_type"].eq("REG")
    ].copy()

    records = []

    for game in games.itertuples(index=False):
        if pd.isna(game.week):
            continue

        week = int(game.week)

        home_team = normalize_team(
            game.home_team
        )

        away_team = normalize_team(
            game.away_team
        )

        records.append(
            {
                "week": week,
                "team": home_team,
                "opponent": away_team,
            }
        )

        records.append(
            {
                "week": week,
                "team": away_team,
                "opponent": home_team,
            }
        )

    schedule = pd.DataFrame(records)

    if schedule.empty:
        raise RuntimeError(
            "No regular-season schedule records "
            f"created for {season}."
        )

    duplicate_count = (
        schedule.duplicated(
            subset=[
                "week",
                "team",
            ]
        ).sum()
    )

    if duplicate_count:
        raise RuntimeError(
            "Schedule contains "
            f"{duplicate_count} duplicate "
            "team-week rows."
        )

    schedule = schedule.sort_values(
        [
            "week",
            "team",
        ]
    ).reset_index(drop=True)

    print(
        "Built complete schedule records for "
        f"{len(schedule)} team-week combinations."
    )

    return schedule
    

def load_scoring_environment(
    games_path,
    season,
):
    """
    Build pregame scoring-environment records from
    nflverse schedule/betting-line data.

    Uses only information attached to the target game:
    total_line and spread_line.

    nflverse convention used by the live site:
    positive spread_line means the home team is favored.
    """

    games_path = Path(games_path)

    if not games_path.exists():
        raise FileNotFoundError(
            "Games file not found: "
            f"{games_path}"
        )

    games = pd.read_csv(games_path)

    required = {
        "season",
        "week",
        "game_type",
        "home_team",
        "away_team",
        "spread_line",
        "total_line",
    }

    missing = sorted(
        required - set(games.columns)
    )

    if missing:
        raise ValueError(
            "Games file missing required columns: "
            f"{missing}"
        )

    games["season"] = pd.to_numeric(
        games["season"],
        errors="coerce",
    )

    games["week"] = pd.to_numeric(
        games["week"],
        errors="coerce",
    )

    games["spread_line"] = pd.to_numeric(
        games["spread_line"],
        errors="coerce",
    )

    games["total_line"] = pd.to_numeric(
        games["total_line"],
        errors="coerce",
    )

    games = games[
        (games["season"] == season)
        & games["game_type"].eq("REG")
    ].copy()

    records = []

    for game in games.itertuples(index=False):
        if pd.isna(game.week):
            continue

        if pd.isna(game.total_line):
            continue

        if pd.isna(game.spread_line):
            continue

        week = int(game.week)

        home_team = normalize_team(
            game.home_team
        )

        away_team = normalize_team(
            game.away_team
        )

        game_total = float(
            game.total_line
        )

        spread_line = float(
            game.spread_line
        )

        home_implied_total = (
            game_total + spread_line
        ) / 2.0

        away_implied_total = (
            game_total - spread_line
        ) / 2.0

        records.append(
            {
                "week": week,
                "team": home_team,
                "opponent": away_team,
                "game_total": game_total,
                "spread_line": spread_line,
                "implied_team_total":
                    home_implied_total,
            }
        )

        records.append(
            {
                "week": week,
                "team": away_team,
                "opponent": home_team,
                "game_total": game_total,
                "spread_line": -spread_line,
                "implied_team_total":
                    away_implied_total,
            }
        )

    environment = pd.DataFrame(records)

    if environment.empty:
        raise RuntimeError(
            "No scoring-environment records "
            f"created for {season}."
        )

    duplicate_count = (
        environment.duplicated(
            subset=[
                "week",
                "team",
            ]
        ).sum()
    )

    if duplicate_count:
        raise RuntimeError(
            "Scoring-environment data contains "
            f"{duplicate_count} duplicate "
            "team-week rows."
        )

    environment = environment.sort_values(
        [
            "week",
            "team",
        ]
    ).reset_index(drop=True)

    print(
        "Built scoring-environment records "
        f"for {len(environment)} "
        "team-week combinations."
    )

    return environment


def attach_scoring_environment(
    dataset,
    scoring_environment,
):
    """
    Attach target-week sportsbook environment to each
    historical player-week row.

    This information is known before the game and does
    not use target-week player performance.
    """

    dataset = dataset.copy()

    dataset["team"] = (
        dataset["team"]
        .map(normalize_team)
    )

    environment = (
        scoring_environment.copy()
    )

    dataset = dataset.merge(
        environment,
        on=[
            "week",
            "team",
        ],
        how="left",
        validate="many_to_one",
    )

    matched = int(
        dataset[
            "implied_team_total"
        ].notna().sum()
    )

    print(
        "Matched scoring environment to "
        f"{matched} of {len(dataset)} "
        "historical player-week rows."
    )

    return dataset


def add_scoring_environment_score(
    dataset,
):
    """
    Match the live site's weekly normalization:

    lowest implied team total = 25
    highest implied team total = 100.
    """

    dataset = dataset.copy()

    dataset[
        "scoring_environment_score"
    ] = np.nan

    for week in sorted(
        dataset["week"].dropna().unique()
    ):
        mask = (
            dataset["week"] == week
        )

        week_rows = dataset.loc[
            mask
        ]

        valid = week_rows[
            "implied_team_total"
        ].dropna()

        if valid.empty:
            continue

        low = float(valid.min())
        high = float(valid.max())

        if high <= low:
            dataset.loc[
                mask
                & dataset[
                    "implied_team_total"
                ].notna(),
                "scoring_environment_score",
            ] = 50.0

            continue

        valid_mask = (
            mask
            & dataset[
                "implied_team_total"
            ].notna()
        )

        dataset.loc[
            valid_mask,
            "scoring_environment_score",
        ] = (
            25.0
            + (
                (
                    dataset.loc[
                        valid_mask,
                        "implied_team_total",
                    ]
                    - low
                )
                / (high - low)
            )
            * 75.0
        ).round()

    return dataset
def add_matchup_scores(
    dataset,
    season_stats,
    schedule,
):
    """
    Reconstruct the historical live-style Matchup signal.

    For target week W:
      - only games from weeks < W are used
      - each defense's PPR allowed is calculated by position
      - the target player's upcoming opponent is identified
        from the complete regular-season schedule
      - defenses are normalized within position to 20-80

    Target-week player performance is never used.
    """

    dataset = dataset.copy()
    stats = season_stats.copy()
    schedule = schedule.copy()

    dataset["matchup_raw"] = np.nan
    dataset["matchup_score"] = np.nan

    stats["team"] = (
        stats["team"]
        .map(normalize_team)
    )

    schedule["team"] = (
        schedule["team"]
        .map(normalize_team)
    )

    schedule["opponent"] = (
        schedule["opponent"]
        .map(normalize_team)
    )

    opponent_lookup = {
        (
            int(row.week),
            row.team,
        ): row.opponent
        for row in schedule.itertuples(
            index=False
        )
    }

    for target_week in sorted(
        dataset["week"].dropna().unique()
    ):
        target_week = int(target_week)

        history = stats[
            stats["week"] < target_week
        ].copy()

        if history.empty:
            continue

        # Total PPR produced by an offense's entire
        # position group in each prior game.
        game_position_ppr = (
            history.groupby(
                [
                    "week",
                    "team",
                    "position",
                ],
                as_index=False,
            )["actual_ppr"]
            .sum()
        )

        defense_records = []

        for row in game_position_ppr.itertuples(
            index=False
        ):
            game_week = int(row.week)

            offense_team = normalize_team(
                row.team
            )

            defense = opponent_lookup.get(
                (
                    game_week,
                    offense_team,
                )
            )

            if not defense:
                continue

            defense_records.append(
                {
                    "defense":
                        normalize_team(defense),

                    "position":
                        row.position,

                    "ppr_allowed":
                        float(row.actual_ppr),
                }
            )

        if not defense_records:
            continue

        defense_df = pd.DataFrame(
            defense_records
        )

        # Average positional PPR allowed per prior
        # game by each defense.
        defense_allowed = (
            defense_df.groupby(
                [
                    "defense",
                    "position",
                ],
                as_index=False,
            )["ppr_allowed"]
            .mean()
            .rename(
                columns={
                    "ppr_allowed":
                        "matchup_raw"
                }
            )
        )

        defense_allowed[
            "matchup_score"
        ] = 50.0

        # Match the live site's 20-80 defensive
        # Matchup normalization within each position.
        for position in POSITIONS:
            position_mask = (
                defense_allowed[
                    "position"
                ] == position
            )

            position_rows = (
                defense_allowed.loc[
                    position_mask
                ]
            )

            if position_rows.empty:
                continue

            low = float(
                position_rows[
                    "matchup_raw"
                ].min()
            )

            high = float(
                position_rows[
                    "matchup_raw"
                ].max()
            )

            if high <= low:
                defense_allowed.loc[
                    position_mask,
                    "matchup_score",
                ] = 50.0

                continue

            defense_allowed.loc[
                position_mask,
                "matchup_score",
            ] = (
                20.0
                + (
                    (
                        position_rows[
                            "matchup_raw"
                        ]
                        - low
                    )
                    / (high - low)
                )
                * 60.0
            ).round()

        raw_lookup = {
            (
                row.defense,
                row.position,
            ): float(row.matchup_raw)
            for row in defense_allowed.itertuples(
                index=False
            )
        }

        score_lookup = {
            (
                row.defense,
                row.position,
            ): float(row.matchup_score)
            for row in defense_allowed.itertuples(
                index=False
            )
        }

        target_mask = (
            dataset["week"] == target_week
        )

        for index in dataset.index[
            target_mask
        ]:
            team = normalize_team(
                dataset.at[
                    index,
                    "team",
                ]
            )

            opponent = opponent_lookup.get(
                (
                    target_week,
                    team,
                )
            )

            if not opponent:
                continue

            position = dataset.at[
                index,
                "position",
            ]

            key = (
                normalize_team(opponent),
                position,
            )

            if key not in raw_lookup:
                continue

            dataset.at[
                index,
                "matchup_raw",
            ] = raw_lookup[key]

            dataset.at[
                index,
                "matchup_score",
            ] = score_lookup[key]

    matched = int(
        dataset[
            "matchup_score"
        ].notna().sum()
    )

    print(
        "Matched historical Matchup signal to "
        f"{matched} of {len(dataset)} "
        "player-week rows."
    )

    return dataset


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
def confidence_usage_value(
    player_row,
    team_rows,
):
    """
    Match the live app.js usage calculation used
    specifically inside Model Confidence.

    This intentionally differs from the standalone
    Usage signal.
    """

    position = player_row["position"]

    carries = float(
        player_row.get("carries", 0) or 0
    )

    targets = float(
        player_row.get("targets", 0) or 0
    )

    attempts = float(
        player_row.get(
            "attempts",
            player_row.get(
                "passing_attempts",
                0
            )
        ) or 0
    )

    team_carries = numeric(
        team_rows["carries"]
    ).sum()

    if position == "QB":
        team_attempts = numeric(
            team_rows["attempts"]
        ).sum()

        passing_share = (
            attempts / team_attempts
            if team_attempts > 0
            else 0.0
        )

        rushing_share = (
            carries / team_carries
            if team_carries > 0
            else 0.0
        )

        return (
            passing_share
            + rushing_share
        )

    if position in {"WR", "TE"}:
        team_targets = numeric(
            team_rows["targets"]
        ).sum()

        if team_targets <= 0:
            return 0.0

        return targets / team_targets

    if team_carries <= 0:
        return 0.0

    return carries / team_carries

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
    scoring_environment,
    schedule,
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

    result = attach_scoring_environment(
        result,
        scoring_environment,
    )

    result = add_scoring_environment_score(
        result
    )
        result = add_matchup_scores(
        result,
        season_stats,
        schedule,
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
        "scoring_environment_score",
        "matchup_score",
        "implied_team_total",
        "game_total",
        "spread_line",
        "opponent",
        "production_raw",
        "opportunity_raw",
        "usage_raw",
        "redzone_raw",
        "matchup_raw",
        "actual_ppr",
    ]

    return result[columns]


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--games",
        required=True,
        help=(
            "nflverse games.csv containing "
            "pregame spread and total lines"
        ),
    )
    
    parser.add_argument(
        "--stats",
        required=True,
        help=(
            "nflverse weekly player stats "
            "CSV or parquet"
        ),
    )
    parser.add_argument(
        "--pbp",
        required=True,
        help=(
            "nflverse play-by-play CSV "
            "or CSV.GZ for red-zone usage"
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
    schedule = load_schedule(
        args.games,
        args.season,
    )
    scoring_environment = (
        load_scoring_environment(
            args.games,
            args.season,
        )
    )
    
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
        scoring_environment,
        schedule,
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
