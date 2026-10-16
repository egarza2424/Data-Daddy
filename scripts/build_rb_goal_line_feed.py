
"""Build pregame four-game red-zone evidence for RB, WR and TE.

This script generates supporting data only. It does not change live scores.
"""
import argparse
import csv
import gzip
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ALIASES = {"LAR": "LA", "JAX": "JAC", "WAS": "WSH"}
POSITIONS = {"RB", "WR", "TE"}
ZONES = ("20_11", "10_6", "5_1")


def norm(value):
    code = str(value or "").strip().upper()
    return ALIASES.get(code, code)


def zone_for_yardline(yard):
    if 11 <= yard <= 20:
        return "20_11"
    if 6 <= yard <= 10:
        return "10_6"
    if 0 < yard <= 5:
        return "5_1"
    return None


def empty_counts():
    return {
        zone: {"carries": 0, "targets": 0}
        for zone in ZONES
    }


def build(pbp_path, stats_path, output_path, target_week):
    with open(stats_path, encoding="utf-8") as handle:
        stats = json.load(handle)

    rows = stats.get("players", [])
    if not isinstance(rows, list):
        raise ValueError("nfl-stats.json players must be a list")

    candidates = {}
    player_games = defaultdict(set)

    for row in rows:
        if str(row.get("position", "")).upper() not in POSITIONS:
            continue

        try:
            season = int(row.get("season", 0))
            week = int(row.get("week", 0))
        except (TypeError, ValueError):
            continue

        if season != 2026 or not 1 <= week < target_week:
            continue

        pid = str(row.get("player_id") or "").strip()
        if not pid:
            continue

        player_games[pid].add(week)

        if pid not in candidates or week > candidates[pid][0]:
            candidates[pid] = (week, row)

    player = defaultdict(empty_counts)
    team = defaultdict(empty_counts)

    opener = gzip.open if str(pbp_path).endswith(".gz") else open

    with opener(pbp_path, "rt", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)

        required = {
            "season", "week", "season_type", "posteam",
            "yardline_100", "rush_attempt", "pass_attempt",
            "rusher_player_id", "receiver_player_id"
        }

        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Missing PBP columns: {sorted(missing)}")

        for play in reader:
            try:
                season = int(float(play["season"]))
                week = int(float(play["week"]))
                yard = float(play["yardline_100"])
            except (TypeError, ValueError):
                continue

            if season != 2026 or play["season_type"] != "REG":
                continue
            if not 1 <= week < target_week:
                continue

            zone = zone_for_yardline(yard)
            if zone is None:
                continue

            offense = norm(play["posteam"])
            if not offense or offense in {"NONE", "NAN"}:
                continue

            events = (
                ("rush_attempt", "rusher_player_id", "carries"),
                ("pass_attempt", "receiver_player_id", "targets"),
            )

            for flag, id_field, kind in events:
                if play[flag] != "1":
                    continue

                pid = str(play[id_field] or "").strip()

                if kind == "targets" and not pid:
                    continue

                team[(offense, week)][zone][kind] += 1

                if pid:
                    player[(pid, week)][zone][kind] += 1

    output = {}

    for pid, (_, row) in sorted(candidates.items()):
        offense = norm(row.get("team") or row.get("recent_team"))
        if not offense:
            continue

        # Most recent four recorded player games, not four calendar weeks.
        weeks = sorted(player_games[pid], reverse=True)[:4]
        if not weeks:
            continue

        zones = {}

        for zone in ZONES:
            carries = sum(
                player[(pid, week)][zone]["carries"]
                for week in weeks
            )
            targets = sum(
                player[(pid, week)][zone]["targets"]
                for week in weeks
            )
            team_carries = sum(
                team[(offense, week)][zone]["carries"]
                for week in weeks
            )
            team_targets = sum(
                team[(offense, week)][zone]["targets"]
                for week in weeks
            )

            zones[zone] = {
                "carries": carries,
                "targets": targets,
                "team_carries": team_carries,
                "team_targets": team_targets,
                "carry_share": (
                    round(carries / team_carries, 4)
                    if team_carries else None
                ),
                "target_share": (
                    round(targets / team_targets, 4)
                    if team_targets else None
                ),
            }

        weighted = sum(
            (zones[zone]["carries"] + zones[zone]["targets"])
            * weight
            for zone, weight in (
                ("20_11", 1),
                ("10_6", 2),
                ("5_1", 3),
            )
        )

        output[pid] = {
            "player_name": (
                row.get("player_display_name")
                or row.get("player_name")
                or pid
            ),
            "position": str(row["position"]).upper(),
            "team": offense,
            "games_evaluated": len(weeks),
            "weeks_evaluated": sorted(weeks),
            "zones": zones,
            "weighted_opportunities": weighted,
            "weighted_opportunities_per_game": round(
                weighted / len(weeks), 4
            ),
        }

    eligible = [
        record["weighted_opportunities_per_game"]
        for record in output.values()
    ]
    league_high = max(eligible, default=0)

    for record in output.values():
        record["red_zone_score"] = (
            round(
                100 * record["weighted_opportunities_per_game"]
                / league_high
            )
            if league_high > 0 else None
        )

    payload = {
        "season": 2026,
        "target_week": target_week,
        "source": "nflverse play_by_play_2026.csv.gz",
        "window": "previous four recorded player games",
        "positions": sorted(POSITIONS),
        "zone_weights": {
            "20_11": 1,
            "10_6": 2,
            "5_1": 3,
        },
        "league_high_weighted_opportunities_per_game": league_high,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "players": output,
    }

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        f"Wrote {len(output)} RB/WR/TE records "
        f"for target Week {target_week}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pbp", required=True)
    parser.add_argument("--stats", default="nfl-stats.json")
    parser.add_argument(
        "--output",
        default="data/red_zone_usage_2026.json",
    )
    parser.add_argument("--target-week", type=int, required=True)

    args = parser.parse_args()

    if not 2 <= args.target_week <= 19:
        parser.error("--target-week must be 2–19")

    build(
        args.pbp,
        args.stats,
        args.output,
        args.target_week,
    )
