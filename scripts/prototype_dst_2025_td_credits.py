#!/usr/bin/env python3
"""Read-only D/ST touchdown attribution prototype for 2025 nflverse PBP.

This is NOT an ESPN scoring engine. Produces candidate team-game touchdown
counts for validation; no fantasy points, rankings, or repository files.
"""
import json
import sys
import duckdb

URL = "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_2025.parquet"

def main():
    source = sys.argv[1] if len(sys.argv) > 1 else URL
    con = duckdb.connect()
    try:
        cols = {r[0] for r in con.execute("DESCRIBE SELECT * FROM read_parquet(?)", [source]).fetchall()}
        required = {"game_id", "week", "season", "play_id", "touchdown", "td_team",
                    "posteam", "defteam", "play_type", "return_touchdown"}
        missing = sorted(required - cols)
        if missing:
            sys.exit("Missing nflverse columns: " + ", ".join(missing))
        rows = con.execute("""
          SELECT game_id, week, play_id, play_type, posteam, defteam,
                 td_team, return_touchdown
          FROM read_parquet(?)
          WHERE season = 2025 AND week BETWEEN 1 AND 18
            AND touchdown = 1 AND td_team IS NOT NULL
            AND posteam IS NOT NULL AND defteam IS NOT NULL
          ORDER BY week, game_id, play_id
        """, [source]).fetchall()
    except Exception as exc:
        sys.exit("D/ST prototype failed: " + str(exc))
    candidate = {}
    unclear = []
    special_types = {"kickoff", "punt", "field_goal"}
    seen = set()
    for game, week, play, kind, offense, defense, scorer, ret in rows:
        key = (game, play)
        if key in seen:
            continue
        seen.add(key)
        # Punt/kickoff/FG TDs count as special-teams candidates for the
        # scoring team, whether it is posteam or defteam.
        if kind in special_types:
            category = "special_teams_td_candidate"
        elif scorer == defense:
            category = "defensive_td_candidate"
        elif scorer == offense:
            continue  # conventional offensive touchdown
        else:
            unclear.append({"game_id": game, "play_id": play, "scorer": scorer})
            continue
        team_key = (game, week, scorer)
        counts = candidate.setdefault(team_key, {"defensive_td_candidate": 0,
                                                  "special_teams_td_candidate": 0})
        counts[category] += 1
    records = [
        {"game_id": game, "week": week, "team": team, **counts}
        for (game, week, team), counts in sorted(candidate.items())
    ]
    totals = {
        category: sum(row[category] for row in records)
        for category in ("defensive_td_candidate", "special_teams_td_candidate")
    }
    print(json.dumps({
        "season": 2025,
        "status": "provisional_attribution_not_verified_espn_scoring",
        "candidate_touchdowns": totals,
        "team_games_with_candidate_tds": len(records),
        "unresolved_td_team_events": unclear[:20],
        "sample_team_games": records[:12],
        "warnings": [
            "Special-teams scoring uses play_type and td_team, not defteam alone.",
            "Counts are candidates; validate against ESPN before awarding fantasy points.",
            "No sacks, turnovers, blocked-kick bonus, safeties or points allowed calculated.",
            "No repository files, rankings, projections, or model weights changed."
        ]
    }, indent=2))

if __name__ == "__main__":
    main()
