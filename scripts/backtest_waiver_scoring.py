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
    print("Status: DATA VALIDATION ONLY")
    print("No live rankings or historical snapshots modified.")


if __name__ == "__main__":
    main()
