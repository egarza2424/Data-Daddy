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
            "name": (
                games[-1].get("player_display_name")
                or games[-1].get("player_name")
                or player_id
            ),
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


def score_historical_signals(signals):
    """Reproduce live position-relative evidence scoring."""
    from collections import defaultdict

    weights = {
        "opportunity_change": 0.45,
        "recent_average_ppr": 0.35,
        "latest_opportunity": 0.20,
    }

    groups = defaultdict(list)
    for signal in signals:
        groups[signal["position"]].append(signal)

    for position, players in groups.items():
        percentile_maps = {}

        for field in weights:
            values = sorted({
                player[field]
                for player in players
                if player[field] is not None
            })

            if not values:
                percentile_maps[field] = {}
            elif len(values) == 1:
                percentile_maps[field] = {values[0]: 50.0}
            else:
                percentile_maps[field] = {
                    value: round(
                        100 * index / (len(values) - 1), 2
                    )
                    for index, value in enumerate(values)
                }

        for player in players:
            score = 0.0

            for field, weight in weights.items():
                value = player[field]

                if value is None:
                    continue

                score += percentile_maps[field][value] * weight

            player["historical_evidence_score"] = round(score, 2)

    return sorted(
        signals,
        key=lambda player: -player["historical_evidence_score"],
    )


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
        known_changes = [
            signal["opportunity_change"]
            for signal in group
            if signal["opportunity_change"] is not None
        ]

        missing_changes = len(group) - len(known_changes)

        if known_changes:
            average_change = sum(known_changes) / len(known_changes)
            positive_changes = sum(
                change > 0 for change in known_changes
            )

            print(
                f"  Opportunity change: "
                f"avg={average_change:+.2f}, "
                f"positive={positive_changes}/{len(known_changes)}, "
                f"missing={missing_changes}"
            )
        else:
            print(
                f"  Opportunity change: no available values, "
                f"missing={missing_changes}"
            )
    ranked = score_historical_signals(signals)

    print("\nHISTORICAL ALL-PLAYER EVIDENCE SCORE — TOP 10")
    print("Diagnostic only: historical ownership eligibility not verified.")
    top_ten = ranked[:10]
    top_ten_positions = Counter(
        player["position"] for player in top_ten
    )

    for rank, player in enumerate(top_ten, start=1):
        print(
            f"{rank:2}. "
            f"{player['name']} ({player['position']}) | "
            f"Score: {player['historical_evidence_score']:.2f} | "
            f"Recent PPR: {player['recent_average_ppr']:.2f} | "
            f"Opportunity change: {player['opportunity_change']}"
        )

    print(f"Top 10 position distribution: {dict(top_ten_positions)}")
    print("\nACTUAL WEEK 6 PPR — HISTORICAL TOP 10")

    actual_week = {}
    duplicate_ids = set()

    for row in rows:
        if int(row["week"]) != target_week:
            continue

        player_id = row["player_id"]

        if player_id in actual_week:
            duplicate_ids.add(player_id)
            continue

        actual_week[player_id] = calculate_ppr(row)

    for rank, player in enumerate(top_ten, start=1):
        player_id = player["player_id"]

        if player_id in duplicate_ids:
            actual = "AMBIGUOUS"
        elif player_id not in actual_week:
            actual = "NO RECORD"
        else:
            actual = f"{actual_week[player_id]:.2f}"

        print(
            f"{rank:2}. {player['position']} | "
            f"Evidence={player['historical_evidence_score']:.2f} | "
            f"Prior PPR={player['recent_average_ppr']:.2f} | "
            f"Actual Week {target_week} PPR={actual}"
        )

    print(
        "Note: NO RECORD is not treated as zero PPR. "
        "Duplicate player-week records are excluded."
    )

    
    print("Status: HISTORICAL SIGNAL VALIDATION")
    print("No live rankings or historical snapshots modified.")



if __name__ == "__main__":
    main()
