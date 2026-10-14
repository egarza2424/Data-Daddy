#!/usr/bin/env python3
"""Read-only historical waiver scoring backtest."""

import argparse
import csv
import io
import urllib.request
from collections import Counter

STATS_URL = (
    "https://github.com/nflverse/nflverse-data/releases/"
    "download/stats_player/stats_player_week_{season}.csv"
)
POSITIONS = {"QB", "RB", "WR", "TE"}


def safe_number(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def calculate_ppr(row):
    """Calculate full-PPR fantasy points from weekly player stats."""
    return round(
        safe_number(row.get("passing_yards")) / 25
        + safe_number(row.get("passing_tds")) * 4
        - safe_number(row.get("interceptions")) * 2
        + safe_number(row.get("rushing_yards")) / 10
        + safe_number(row.get("rushing_tds")) * 6
        + safe_number(row.get("receptions"))
        + safe_number(row.get("receiving_yards")) / 10
        + safe_number(row.get("receiving_tds")) * 6,
        2,
    )


def calculate_opportunity(row):
    """Estimate opportunity volume from touches and targets."""
    position = row.get("position")

    if position == "QB":
        return (
            safe_number(row.get("attempts"))
            + safe_number(row.get("carries"))
        )

    return (
        safe_number(row.get("carries"))
        + safe_number(row.get("targets"))
    )


def build_historical_signals(rows, target_week):
    """Build pregame signals without using the target week's results."""
    from collections import defaultdict

    history = defaultdict(list)

    for row in rows:
        week = int(row["week"])

        if week >= target_week:
            continue

        history[row["player_id"]].append(row)

    signals = []

    for player_id, games in history.items():
        games.sort(key=lambda game: int(game["week"]))

        recent = games[-3:]
        previous = games[-4:-1]

        recent_ppr = [
            calculate_ppr(game)
            for game in recent
        ]

        recent_opportunity = [
            calculate_opportunity(game)
            for game in recent
        ]

        previous_opportunity = [
            calculate_opportunity(game)
            for game in previous
        ]

        latest_opportunity = recent_opportunity[-1]

        recent_average_ppr = (
            sum(recent_ppr) / len(recent_ppr)
        )

        recent_average_opportunity = (
            sum(recent_opportunity) / len(recent_opportunity)
        )

        previous_average_opportunity = (
            sum(previous_opportunity) / len(previous_opportunity)
            if previous_opportunity
            else 0
        )

        opportunity_change = (
            latest_opportunity - previous_average_opportunity
            if previous_opportunity
            else None
        )

        signals.append({
            "player_id": player_id,
            "position": games[-1]["position"],
            "target_week": target_week,
            "recent_average_ppr": round(recent_average_ppr, 2),
            "latest_opportunity": round(latest_opportunity, 2),
            "opportunity_change": (
                round(opportunity_change, 2)
                if opportunity_change is not None
                else None
            ),
            "history_games": len(games),
        })

    return signals


def load_historical_stats(season):

    url = STATS_URL.format(season=season)

    with urllib.request.urlopen(url, timeout=60) as response:
        content = response.read().decode("utf-8-sig")

    rows = list(csv.DictReader(io.StringIO(content)))
    if not rows:
        raise ValueError("Historical player dataset is empty.")

    required = {
        "player_id",
        "position",
        "season",
        "week",
        "season_type",
        "receptions",
        "receiving_yards",
        "rushing_yards",
        "passing_yards",
    }

    missing = required - set(rows[0])
    if missing:
        raise ValueError(
            f"Historical dataset missing columns: {sorted(missing)}"
        )

    return [
        row
        for row in rows
        if row.get("position") in POSITIONS
        and row.get("season_type") == "REG"
        and int(row["season"]) == season
    ]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", type=int, default=2025)
    args = parser.parse_args()

    rows = load_historical_stats(args.season)

    weeks = sorted({int(row["week"]) for row in rows})
    positions = Counter(row["position"] for row in rows)

    print(f"Historical season: {args.season}")
    print(f"Player-week records: {len(rows)}")
    print(f"Available weeks: {weeks}")
    print(f"Position distribution: {dict(positions)}")

    target_week = 6
    signals = build_historical_signals(rows, target_week)

    signal_positions = Counter(
        signal["position"] for signal in signals
    )

    print(f"Pregame target week: {target_week}")
    print(f"Players with historical signals: {len(signals)}")
    print(f"Signal position distribution: {dict(signal_positions)}")

    for position in sorted(POSITIONS):
        group = [
            signal for signal in signals
            if signal["position"] == position
        ]

        if not group:
            continue

        average_ppr = sum(
            signal["recent_average_ppr"] for signal in group
        ) / len(group)

        average_opportunity = sum(
            signal["latest_opportunity"] for signal in group
        ) / len(group)

        print(
            f"{position}: {len(group)} players, "
            f"avg recent PPR={average_ppr:.2f}, "
            f"avg latest opportunity={average_opportunity:.2f}"
        )

    print("Status: HISTORICAL SIGNAL VALIDATION")
    print("No live rankings or historical snapshots modified.")



if __name__ == "__main__":
    main()
