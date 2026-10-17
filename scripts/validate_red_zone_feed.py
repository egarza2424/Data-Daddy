import argparse
import csv
import gzip
import json
from collections import defaultdict
from pathlib import Path

WEIGHTS = {"20_11": 1, "10_6": 2, "5_1": 3}
ALIASES = {"LAR": "LA", "JAX": "JAC", "WAS": "WSH"}


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
    return {zone: {"carries": 0, "targets": 0} for zone in WEIGHTS}


def compare(actual, expected, label, issues, tolerance=0):
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        equal = abs(actual - expected) <= tolerance
    else:
        equal = actual == expected
    if not equal:
        issues.append(f"{label}: feed={actual!r}, source={expected!r}")


def main(args):
    feed = json.loads(Path(args.feed).read_text(encoding="utf-8"))
    stats = json.loads(Path(args.stats).read_text(encoding="utf-8"))
    target_week = int(feed["target_week"])
    if int(feed["season"]) != 2026:
        raise ValueError("This validator currently supports the 2026 season")
    if not isinstance(feed.get("players"), dict):
        raise ValueError("Expected feed.players to be a dictionary")
    if not isinstance(stats.get("players"), list):
        raise ValueError("Expected stats.players to be a list")

    player_weeks = defaultdict(set)
    latest = {}
    for row in stats["players"]:
        if str(row.get("position", "")).upper() not in {"RB", "WR", "TE"}:
            continue
        try:
            season, week = int(row.get("season", 0)), int(row.get("week", 0))
        except (ValueError, TypeError):
            continue
        if season != 2026 or not 1 <= week < target_week:
            continue
        pid = str(row.get("player_id") or "").strip()
        if not pid:
            continue
        player_weeks[pid].add(week)
        if pid not in latest or week > latest[pid][0]:
            latest[pid] = (week, row)

    players = defaultdict(empty_counts)
    teams = defaultdict(empty_counts)
    opener = gzip.open if str(args.pbp).endswith(".gz") else open
    with opener(args.pbp, "rt", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"season", "week", "season_type", "posteam", "yardline_100",
                    "rush_attempt", "pass_attempt", "rusher_player_id", "receiver_player_id"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Missing PBP columns: {sorted(missing)}")
        for play in reader:
            try:
                season = int(float(play["season"]))
                week = int(float(play["week"]))
                yard = float(play["yardline_100"])
            except (ValueError, TypeError):
                continue
            if season != 2026 or play["season_type"] != "REG" or not 1 <= week < target_week:
                continue
            zone = zone_for_yardline(yard)
            if zone is None:
                continue
            offense = norm(play["posteam"])
            if not offense or offense in {"NONE", "NAN"}:
                continue
            for flag, id_field, kind in (
                ("rush_attempt", "rusher_player_id", "carries"),
                ("pass_attempt", "receiver_player_id", "targets"),
            ):
                if play[flag] != "1":
                    continue
                pid = str(play[id_field] or "").strip()
                if kind == "targets" and not pid:
                    continue
                teams[(offense, week)][zone][kind] += 1
                if pid:
                    players[(pid, week)][zone][kind] += 1

    issues_by_player = {}
    all_rates = []
    calculated = {}
    feed_players = feed["players"]
    for pid, (_, row) in sorted(latest.items()):
        team = norm(row.get("team") or row.get("recent_team"))
        if not team:
            continue
        weeks = sorted(player_weeks[pid], reverse=True)[:4]
        zones = {}
        for zone in WEIGHTS:
            carries = sum(players[(pid, w)][zone]["carries"] for w in weeks)
            targets = sum(players[(pid, w)][zone]["targets"] for w in weeks)
            team_carries = sum(teams[(team, w)][zone]["carries"] for w in weeks)
            team_targets = sum(teams[(team, w)][zone]["targets"] for w in weeks)
            zones[zone] = {
                "carries": carries, "targets": targets,
                "team_carries": team_carries, "team_targets": team_targets,
                "carry_share": round(carries / team_carries, 4) if team_carries else None,
                "target_share": round(targets / team_targets, 4) if team_targets else None,
            }
        weighted = sum((zones[z]["carries"] + zones[z]["targets"]) * weight
                       for z, weight in WEIGHTS.items())
        rate = round(weighted / len(weeks), 4)
        calculated[pid] = (row, team, weeks, zones, weighted, rate)
        all_rates.append(rate)

    league_high = max(all_rates, default=0)
    global_issues = []
    compare(feed.get("league_high_weighted_opportunities_per_game"), league_high,
            "league_high_weighted_opportunities_per_game", global_issues, 0.00001)
    compare(set(feed_players), set(calculated), "player ID coverage", global_issues)

    for pid, (row, team, weeks, zones, weighted, rate) in calculated.items():
        record = feed_players.get(pid)
        if record is None:
            continue
        issues = []
        name = record.get("player_name", pid)
        compare(record.get("position"), str(row["position"]).upper(), "position", issues)
        compare(record.get("team"), team, "team", issues)
        compare(record.get("games_evaluated"), len(weeks), "games_evaluated", issues)
        compare(record.get("weeks_evaluated"), sorted(weeks), "weeks_evaluated", issues)
        compare(record.get("weighted_opportunities"), weighted, "weighted_opportunities", issues)
        compare(record.get("weighted_opportunities_per_game"), rate,
                "weighted_opportunities_per_game", issues, 0.00001)
        expected_score = round(100 * rate / league_high) if league_high > 0 else None
        compare(record.get("red_zone_score"), expected_score, "red_zone_score", issues)
        for zone in WEIGHTS:
            actual_zone = record.get("zones", {}).get(zone, {})
            for field, value in zones[zone].items():
                compare(actual_zone.get(field), value, f"{zone}.{field}", issues,
                        0.00001 if field.endswith("_share") else 0)
        if issues:
            issues_by_player[pid] = (name, issues)

    print(f"RED-ZONE FEED VALIDATION | 2026 Week {target_week}")
    print(f"Players: {len(feed_players)} in feed, {len(calculated)} independently calculated")
    print(f"League-high weighted opportunities/game: {league_high}")
    print(f"Player records with mismatches: {len(issues_by_player)}")
    for issue in global_issues:
        print(f"GLOBAL FAIL: {issue}")
    for pid, (name, issues) in issues_by_player.items():
        print(f"FAIL {name} ({pid})")
        for issue in issues:
            print(f"  {issue}")
    if not global_issues and not issues_by_player:
        print("RESULT: PASS — all player records match the independently recounted source")
    else:
        print("RESULT: FAIL — discrepancies found")
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pbp", required=True)
    parser.add_argument("--stats", default="nfl-stats.json")
    parser.add_argument("--feed", required=True)
    main(parser.parse_args())
