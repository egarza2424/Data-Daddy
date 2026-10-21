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
    """Match the live opportunity formulas by position."""
    position = row.get("position")

    if position == "QB":
        return (
            safe_number(row.get("attempts"))
            + safe_number(row.get("carries"))
        )

    if position == "RB":
        return (
            safe_number(row.get("carries"))
            + safe_number(row.get("targets"))
        )

    return safe_number(row.get("targets"))



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
    
    # Controlled historical opportunity-stability experiment.
    # Diagnostic only: historical ownership eligibility is unverified.
    print("\nCONTROLLED OPPORTUNITY-STABILITY BACKTEST")
    print("All-player diagnostic; NOT verified waiver precision.")

    from collections import defaultdict
    import statistics

    experiment_results = defaultdict(list)
    weeks_compared = 0

    for test_week in range(4, 19):
        historical_signals = build_historical_signals(
            rows, test_week
        )
        if len(historical_signals) < 20:
            continue

        baseline_ranked = score_historical_signals(
            [dict(player) for player in historical_signals]
        )

        challenger_signals = [
            dict(player) for player in historical_signals
        ]

        # Shrink opportunity spikes when history is limited.
        # This is a test hypothesis, not a validated weight.
        for player in challenger_signals:
            change = player["opportunity_change"]
            if change is not None:
                reliability = min(
                    1.0, max(0.0, player["history_games"] - 1) / 4
                )
                player["opportunity_change"] = (
                    change * reliability
                )

        challenger_ranked = score_historical_signals(
            challenger_signals
        )

        actual = defaultdict(list)
        for game in rows:
            if int(game["week"]) == test_week:
                actual[game["player_id"]].append(
                    calculate_ppr(game)
                )

        # Only unique, observed player-week outcomes qualify.
        observed = {
            player_id: values[0]
            for player_id, values in actual.items()
            if len(values) == 1
        }

        position_outcomes = defaultdict(list)
        for player in historical_signals:
            player_id = player["player_id"]
            if player_id in observed:
                position_outcomes[player["position"]].append(
                    observed[player_id]
                )

        position_medians = {
            position: statistics.median(values)
            for position, values in position_outcomes.items()
            if values
        }

        if not position_medians:
            continue

        for model_name, ranked_players in (
            ("Baseline 45/35/20", baseline_ranked),
            ("Stability challenger", challenger_ranked),
        ):
            top_ten = ranked_players[:10]
            advantages = []

            for player in top_ten:
                player_id = player["player_id"]
                position = player["position"]
                if (
                    player_id in observed
                    and position in position_medians
                ):
                    advantages.append(
                        observed[player_id]
                        - position_medians[position]
                    )

            experiment_results[model_name].append({
                "week": test_week,
                "observed": len(advantages),
                "total": len(top_ten),
                "advantage": (
                    sum(advantages) / len(advantages)
                    if advantages else None
                ),
            })

        weeks_compared += 1

    print(f"Weeks evaluated: {weeks_compared}")

    for model_name, weekly_results in experiment_results.items():
        valid = [
            result for result in weekly_results
            if result["advantage"] is not None
        ]
        observed_count = sum(
            result["observed"] for result in weekly_results
        )
        total_count = sum(
            result["total"] for result in weekly_results
        )
        mean_advantage = (
            statistics.mean(
                result["advantage"] for result in valid
            )
            if valid else None
        )

        print(f"\n{model_name}")
        print(f"Observed outcomes: {observed_count}/{total_count}")
        print(
            "Mean weekly position-median advantage: "
            + (
                f"{mean_advantage:+.3f} PPR"
                if mean_advantage is not None
                else "UNAVAILABLE"
            )
        )

    print(
        "\nLimitations: no historical ownership filtering; "
        "missing outcomes excluded; no statistical significance "
        "or out-of-sample tuning established."
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
    print("\nMULTIWEEK ALL-PLAYER TOP 10 POSITION AUDIT")
    print("Diagnostic only: historical ownership not verified.")

    total_top_ten = Counter()
    total_pool = Counter()
    weeks_tested = 0

    for week in range(2, 19):
        weekly_signals = build_historical_signals(rows, week)

        if not weekly_signals:
            continue

        weekly_ranked = score_historical_signals(weekly_signals)
        weekly_top = weekly_ranked[:10]

        pool_counts = Counter(
            player["position"] for player in weekly_signals
        )
        top_counts = Counter(
            player["position"] for player in weekly_top
        )

        total_pool.update(pool_counts)
        total_top_ten.update(top_counts)
        weeks_tested += 1

        print(
            f"Week {week:2}: "
            f"pool={len(weekly_signals)}, "
            f"Top 10={dict(top_counts)}"
        )

    print(f"Weeks tested: {weeks_tested}")

    for position in sorted(POSITIONS):
        pool_total = sum(total_pool.values())
        top_total = sum(total_top_ten.values())

        pool_share = (
            100 * total_pool[position] / pool_total
            if pool_total else 0
        )
        top_share = (
            100 * total_top_ten[position] / top_total
            if top_total else 0
        )

        print(
            f"{position}: "
            f"pool share={pool_share:.1f}%, "
            f"Top 10 share={top_share:.1f}%, "
            f"difference={top_share - pool_share:+.1f} pp"
        )
    print("\nMULTIWEEK TOP 10 — ACTUAL NEXT-WEEK PPR")
    print("All-player diagnostic; ownership eligibility not verified.")

    outcomes = {position: [] for position in POSITIONS}
    missing_outcomes = Counter()
    ambiguous_outcomes = Counter()

    for week in range(2, 19):
        weekly_signals = build_historical_signals(rows, week)

        if not weekly_signals:
            continue

        weekly_top = score_historical_signals(weekly_signals)[:10]

        actual_by_id = {}
        duplicate_ids = set()

        for row in rows:
            if int(row["week"]) != week:
                continue

            player_id = row["player_id"]

            if player_id in actual_by_id:
                duplicate_ids.add(player_id)
            else:
                actual_by_id[player_id] = calculate_ppr(row)

        for player in weekly_top:
            position = player["position"]
            player_id = player["player_id"]

            if player_id in duplicate_ids:
                ambiguous_outcomes[position] += 1
            elif player_id not in actual_by_id:
                missing_outcomes[position] += 1
            else:
                outcomes[position].append(actual_by_id[player_id])

    for position in sorted(POSITIONS):
        values = outcomes[position]
        average = sum(values) / len(values) if values else 0

        print(
            f"{position}: "
            f"observed={len(values)}, "
            f"avg actual PPR={average:.2f}, "
            f"missing={missing_outcomes[position]}, "
            f"ambiguous={ambiguous_outcomes[position]}"
        )

    print("Missing or ambiguous outcomes excluded from averages.")
    print("\nMULTIWEEK TOP 10 — POSITION-RELATIVE PPR")
    print("Comparison: same-week, same-position median actual PPR.")

    from statistics import median

    relative_results = {position: [] for position in POSITIONS}

    for week in range(2, 19):
        weekly_signals = build_historical_signals(rows, week)

        if not weekly_signals:
            continue

        weekly_top = score_historical_signals(weekly_signals)[:10]

        week_rows = [
            row for row in rows
            if int(row["week"]) == week
        ]

        week_counts = Counter(row["player_id"] for row in week_rows)

        actual_by_id = {
            row["player_id"]: calculate_ppr(row)
            for row in week_rows
            if week_counts[row["player_id"]] == 1
        }

        position_actuals = {position: [] for position in POSITIONS}

        for row in week_rows:
            if row["player_id"] not in actual_by_id:
                continue

            position_actuals[row["position"]].append(
                actual_by_id[row["player_id"]]
            )

        position_medians = {
            position: median(values)
            for position, values in position_actuals.items()
            if values
        }

        for player in weekly_top:
            position = player["position"]
            player_id = player["player_id"]

            if (
                player_id not in actual_by_id
                or position not in position_medians
            ):
                continue

            relative_results[position].append(
                actual_by_id[player_id] - position_medians[position]
            )

    for position in sorted(POSITIONS):
        values = relative_results[position]

        if not values:
            print(f"{position}: no observed comparisons")
            continue

        average = sum(values) / len(values)
        positive = sum(value > 0 for value in values)

        print(
            f"{position}: "
            f"observed={len(values)}, "
            f"avg above position median={average:+.2f} PPR, "
            f"above median={positive}/{len(values)}"
        )

    print("Only observed, unambiguous outcomes included.")
    print("This is not an ownership-filtered waiver accuracy test.")
    print("\nHIGHEST-RANKED WR OUTSIDE TOP 10")
    print("All-player diagnostic; ownership not verified.")

    overlooked_wr_results = []
    missing_wr_results = 0

    for week in range(2, 19):
        weekly_signals = build_historical_signals(rows, week)

        if not weekly_signals:
            continue

        ranked = score_historical_signals(weekly_signals)

        overlooked = next(
            (
                player for player in ranked[10:]
                if player["position"] == "WR"
            ),
            None
        )

        if overlooked is None:
            continue

        week_rows = [
            row for row in rows
            if int(row["week"]) == week
            and row["player_id"] == overlooked["player_id"]
        ]

        if len(week_rows) != 1:
            missing_wr_results += 1
            continue

        actual_ppr = calculate_ppr(week_rows[0])
        overlooked_wr_results.append(actual_ppr)

        print(
            f"Week {week:2}: {overlooked['name']} | "
            f"Score={overlooked['historical_evidence_score']:.2f} | "
            f"Actual PPR={actual_ppr:.2f}"
        )

    if overlooked_wr_results:
        average = (
            sum(overlooked_wr_results) / len(overlooked_wr_results)
        )

        print(
            f"Observed={len(overlooked_wr_results)}, "
            f"average actual PPR={average:.2f}, "
            f"missing/ambiguous={missing_wr_results}"
        )
    else:
        print("No observed outcomes available.")
    print("\nCONTROLLED TE-TO-WR SWAP — HISTORICAL TEST")
    print("Diagnostic only; historical ownership not verified.")

    swap_differences = []
    skipped_swaps = 0

    for week in range(2, 19):
        weekly_signals = build_historical_signals(rows, week)
        if not weekly_signals:
            continue

        ranked = score_historical_signals(weekly_signals)
        top_ten = ranked[:10]

        selected_tes = [
            player for player in top_ten
            if player["position"] == "TE"
        ]

        if len(selected_tes) < 3:
            continue

        removed_te = selected_tes[-1]

        added_wr = next(
            (
                player for player in ranked[10:]
                if player["position"] == "WR"
            ),
            None
        )

        if added_wr is None:
            continue

        relevant_ids = {
            removed_te["player_id"],
            added_wr["player_id"],
        }

        actual_rows = [
            row for row in rows
            if int(row["week"]) == week
            and row["player_id"] in relevant_ids
        ]

        actual_counts = Counter(
            row["player_id"] for row in actual_rows
        )

        if any(
            actual_counts[player_id] != 1
            for player_id in relevant_ids
        ):
            skipped_swaps += 1
            continue

        actual_ppr = {
            row["player_id"]: calculate_ppr(row)
            for row in actual_rows
        }

        te_ppr = actual_ppr[removed_te["player_id"]]
        wr_ppr = actual_ppr[added_wr["player_id"]]
        difference = wr_ppr - te_ppr

        swap_differences.append(difference)

        print(
            f"Week {week:2}: "
            f"OUT {removed_te['name']} (TE) {te_ppr:.2f} | "
            f"IN {added_wr['name']} (WR) {wr_ppr:.2f} | "
            f"Change={difference:+.2f} PPR"
        )

    if swap_differences:
        average_change = (
            sum(swap_differences) / len(swap_differences)
        )
        improved = sum(
            difference > 0 for difference in swap_differences
        )

        print(
            f"Evaluated={len(swap_differences)}, "
            f"improved={improved}, "
            f"avg PPR change={average_change:+.2f}, "
            f"skipped={skipped_swaps}"
        )
    else:
        print(f"No valid swaps; skipped={skipped_swaps}")

    # ---------------------------------------------------------
    # CONTROLLED RB EVIDENCE VS J2 HISTORICAL COMPARISON
    # ---------------------------------------------------------
    print("\nCONTROLLED RB EVIDENCE VS J2 BACKTEST")
    print("All-player diagnostic; ownership not verified.")

    j2_url = (
        "https://raw.githubusercontent.com/"
        "egarza2424/Data-Daddy/main/"
        "projection-model/validation/"
        "2025-rb-model-j2-predictions.csv"
    )

    if args.season != 2025:
        print("Skipped: J2 comparison currently supports 2025.")
    else:
        with urllib.request.urlopen(
            j2_url, timeout=60
        ) as response:
            j2_text = response.read().decode("utf-8-sig")

        j2_rows = list(csv.DictReader(io.StringIO(j2_text)))

        j2_predictions = {}
        duplicate_keys = set()

        for record in j2_rows:
            if record.get("model") != "J2_RB_role_stability":
                continue

            week = int(record["week"])
            cutoff = int(record["training_through_week"])
            player_id = record["player_id"]
            key = (week, player_id)

            if not 7 <= week <= 18:
                continue

            if cutoff >= week:
                raise ValueError(
                    f"Invalid J2 training cutoff: {key}"
                )

            if key in j2_predictions:
                duplicate_keys.add(key)
                continue

            j2_predictions[key] = float(
                record["projected_ppr"]
            )

        for key in duplicate_keys:
            del j2_predictions[key]

        print(f"Valid J2 predictions: {len(j2_predictions)}")
        print(f"Duplicate J2 keys excluded: {len(duplicate_keys)}")

        actual_lookup = {}
        actual_counts = Counter()

        for record in rows:
            key = (
                int(record["week"]),
                record["player_id"]
            )
            actual_counts[key] += 1
            actual_lookup[key] = calculate_ppr(record)

        evidence_results = []
        j2_results = []
        weekly_winners = Counter()
        total_matched = 0
        weeks_evaluated = 0

        for week in range(7, 19):
            weekly_signals = build_historical_signals(
                rows, week
            )
            scored = score_historical_signals(
                weekly_signals
            )

            matched = []

            for player in scored:
                if player["position"] != "RB":
                    continue

                key = (week, player["player_id"])

                if key not in j2_predictions:
                    continue

                if actual_counts[key] != 1:
                    continue

                matched.append({
                    "player_id": player["player_id"],
                    "name": player["name"],
                    "evidence": player[
                        "historical_evidence_score"
                    ],
                    "j2": j2_predictions[key],
                    "actual": actual_lookup[key],
                })

            if len(matched) < 10:
                print(
                    f"Week {week}: skipped; "
                    f"only {len(matched)} matched RBs"
                )
                continue

            total_matched += len(matched)
            weeks_evaluated += 1

            evidence_top = sorted(
                matched,
                key=lambda p: (
                    -p["evidence"], p["player_id"]
                )
            )[:10]

            j2_top = sorted(
                matched,
                key=lambda p: (
                    -p["j2"], p["player_id"]
                )
            )[:10]

            evidence_avg = sum(
                p["actual"] for p in evidence_top
            ) / 10

            j2_avg = sum(
                p["actual"] for p in j2_top
            ) / 10

            evidence_results.append(evidence_avg)
            j2_results.append(j2_avg)

            if evidence_avg > j2_avg:
                weekly_winners["Evidence"] += 1
            elif j2_avg > evidence_avg:
                weekly_winners["J2"] += 1
            else:
                weekly_winners["Tie"] += 1

            overlap = len(
                {p["player_id"] for p in evidence_top}
                & {p["player_id"] for p in j2_top}
            )

            print(
                f"Week {week}: n={len(matched)}, "
                f"Evidence={evidence_avg:.2f}, "
                f"J2={j2_avg:.2f}, "
                f"J2-Evidence={j2_avg-evidence_avg:+.2f}, "
                f"Top10 overlap={overlap}/10"
            )

        if weeks_evaluated:
            evidence_mean = (
                sum(evidence_results) / weeks_evaluated
            )
            j2_mean = (
                sum(j2_results) / weeks_evaluated
            )

            print(
                f"\nWeeks evaluated: {weeks_evaluated}"
            )
            print(f"Matched RB rows: {total_matched}")
            print(
                f"Evidence Top10 mean actual PPR: "
                f"{evidence_mean:.3f}"
            )
            print(
                f"J2 Top10 mean actual PPR: "
                f"{j2_mean:.3f}"
            )
            print(
                f"J2 minus Evidence: "
                f"{j2_mean-evidence_mean:+.3f} PPR"
            )
            print(
                f"Weekly winners: {dict(weekly_winners)}"
            )
        else:
            print("No comparable weeks available.")

        print(
            "Limitations: no historical ownership filter; "
            "comparison conditions on observed outcomes; "
            "J2 feature-time integrity not independently audited."
        )


    
    
    print("Status: HISTORICAL SIGNAL VALIDATION")
    print("No live rankings or historical snapshots modified.")



if __name__ == "__main__":
    main()
