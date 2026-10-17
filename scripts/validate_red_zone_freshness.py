"""Fail closed when completed pre-target-week games are missing source coverage."""
import argparse
import csv
import gzip
import io
import json
import urllib.request
from collections import defaultdict
from pathlib import Path

SCHEDULE_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
ALIASES = {"LA": "LAR", "JAC": "JAX", "WSH": "WAS"}


def team_code(value):
    code = str(value or "").strip().upper()
    return ALIASES.get(code, code)


def load_schedule(path):
    if path:
        return Path(path).read_text(encoding="utf-8")
    with urllib.request.urlopen(SCHEDULE_URL, timeout=45) as response:
        return response.read().decode("utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pbp", required=True)
    parser.add_argument("--stats", required=True)
    parser.add_argument("--target-week", required=True, type=int)
    parser.add_argument("--schedule", help="Optional local games.csv for reproducible tests")
    args = parser.parse_args()
    if not 2 <= args.target_week <= 19:
        parser.error("--target-week must be 2-19")

    expected = {}
    for row in csv.DictReader(io.StringIO(load_schedule(args.schedule))):
        try:
            season = int(row.get("season") or 0)
            week = int(row.get("week") or 0)
        except ValueError:
            continue
        if season != 2026 or not 1 <= week < args.target_week:
            continue
        if row.get("game_type") not in ("REG", ""):
            continue
        game_id = str(row.get("game_id") or "").strip()
        home, away = team_code(row.get("home_team")), team_code(row.get("away_team"))
        if not game_id or not home or not away:
            raise RuntimeError(f"Schedule lacks game ID or teams for Week {week}")
        if row.get("home_score") in (None, "") or row.get("away_score") in (None, ""):
            raise RuntimeError(f"Earlier-week game not final: {game_id} (Week {week})")
        expected[game_id] = (week, home, away)
    if not expected:
        raise RuntimeError("No completed earlier-week games found in schedule")

    opener = gzip.open if str(args.pbp).endswith(".gz") else open
    pbp_games = set()
    with opener(args.pbp, "rt", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"game_id", "season", "week", "season_type", "posteam"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise RuntimeError(f"PBP missing required columns: {sorted(missing)}")
        for row in reader:
            game_id = str(row.get("game_id") or "").strip()
            if game_id in expected and row.get("season_type") == "REG":
                pbp_games.add(game_id)

    stats = json.loads(Path(args.stats).read_text(encoding="utf-8"))
    if not isinstance(stats.get("players"), list):
        raise RuntimeError("Expected stats.players to be a list")
    stats_team_weeks = set()
    for row in stats["players"]:
        try:
            season = int(row.get("season") or 0)
            week = int(row.get("week") or 0)
        except (ValueError, TypeError):
            continue
        if season == 2026 and 1 <= week < args.target_week:
            team = team_code(row.get("team") or row.get("recent_team"))
            if team:
                stats_team_weeks.add((week, team))

    missing_pbp = sorted(set(expected) - pbp_games)
    missing_stats = sorted({(week, team) for week, home, away in expected.values()
                            for team in (home, away)} - stats_team_weeks)
    print(f"RED-ZONE FRESHNESS | 2026 Week {args.target_week}")
    print(f"Earlier completed games: {len(expected)}")
    print(f"PBP games covered: {len(pbp_games)}")
    print(f"Missing PBP games: {missing_pbp}")
    print(f"Missing stats team-weeks: {missing_stats}")
    if missing_pbp or missing_stats:
        raise SystemExit("RESULT: FAIL — incomplete pregame source coverage")
    print("RESULT: PASS — all earlier completed games represented in PBP and stats")
    print("Note: coverage does not prove every play or player row is complete.")


if __name__ == "__main__":
    main()
