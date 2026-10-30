#!/usr/bin/env python3
"""Read-only 2025 D/ST core event coverage by team-game.

Counts candidate sacks, interceptions, recovered opponent fumbles and safeties.
No ESPN fantasy points, blocked-kick credits, points-allowed tiers, or writes.
"""
import json
import sys
import duckdb

URL = "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_2025.parquet"

def main():
    source = sys.argv[1] if len(sys.argv) > 1 else URL
    con = duckdb.connect()
    required = {"season", "week", "game_id", "defteam", "posteam", "sack",
                "interception", "fumble_lost", "fumble_recovery_1_team",
                "fumble_recovery_2_team", "safety"}
    try:
        columns = {r[0] for r in con.execute("DESCRIBE SELECT * FROM read_parquet(?)", [source]).fetchall()}
        missing = sorted(required - columns)
        if missing:
            sys.exit("Missing required columns: " + ", ".join(missing))
        rows = con.execute("""
            SELECT game_id, week, defteam AS team,
              COUNT(*) FILTER (WHERE sack = 1) AS sack_candidates,
              COUNT(*) FILTER (WHERE interception = 1) AS interception_candidates,
              COUNT(*) FILTER (WHERE fumble_lost = 1 AND
                (COALESCE(fumble_recovery_1_team = defteam, FALSE)
                 OR COALESCE(fumble_recovery_2_team = defteam, FALSE))) AS recovered_fumble_candidates,
              COUNT(*) FILTER (WHERE safety = 1) AS safety_play_candidates
            FROM read_parquet(?)
            WHERE season = 2025 AND week BETWEEN 1 AND 18
              AND game_id IS NOT NULL AND defteam IS NOT NULL
              AND posteam IS NOT NULL AND defteam <> posteam
            GROUP BY 1,2,3 ORDER BY week, game_id, team
        """, [source]).fetchall()
    except Exception as exc:
        sys.exit("Core event audit failed: " + str(exc))
    fields = ("sack_candidates", "interception_candidates",
              "recovered_fumble_candidates", "safety_play_candidates")
    totals = {name: sum(row[i + 3] for row in rows) for i, name in enumerate(fields)}
    print(json.dumps({
        "scope": "2025 regular season, provisional D/ST event attribution",
        "team_games": len(rows),
        "teams": len({row[2] for row in rows}),
        "candidate_totals": totals,
        "sample_team_games": [
            dict(zip(("game_id", "week", "team") + fields, row)) for row in rows[:8]
        ],
        "warnings": [
            "Safety attribution is not yet verified against the scoring team.",
            "Sacks and turnovers are candidate counts, not verified ESPN credits.",
            "Blocked kicks, touchdowns, and points-allowed scoring are excluded.",
            "No fantasy points, model weights, projections, rankings or repository files changed."
        ]
    }, indent=2))

if __name__ == "__main__":
    main()
