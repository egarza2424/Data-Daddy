#!/usr/bin/env python3
"""Read-only 2025 nflverse blocked-kick and points-allowed field audit.

Reports candidate blocked-kick flags and field availability. Does not infer
ESPN points allowed from opponent final score or award fantasy points.
"""
import json
import sys
import duckdb

SOURCE = "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_2025.parquet"

def main():
    source = sys.argv[1] if len(sys.argv) > 1 else SOURCE
    con = duckdb.connect()
    try:
        columns = {r[0] for r in con.execute("DESCRIBE SELECT * FROM read_parquet(?)", [source]).fetchall()}
        relevant = ["field_goal_result", "punt_blocked", "field_goal_attempt", "extra_point_result",
                    "posteam", "defteam", "game_id", "week", "season",
                    "total_home_score", "total_away_score", "home_score", "away_score",
                    "safety", "td_team", "touchdown", "play_type"]
        present = [name for name in relevant if name in columns]
        missing = [name for name in relevant if name not in columns]
        needed = {"season", "week", "game_id", "defteam", "posteam"}
        if not needed.issubset(columns):
            sys.exit("Missing essential fields: " + ", ".join(sorted(needed - columns)))
        expressions = [
            "COUNT(DISTINCT game_id) AS games",
            "COUNT(DISTINCT game_id || ':' || defteam) AS team_games",
        ]
        if "punt_blocked" in columns:
            expressions.append("COUNT(*) FILTER (WHERE punt_blocked = 1) AS punt_blocked_candidates")
        if "field_goal_result" in columns:
            expressions.append("COUNT(*) FILTER (WHERE field_goal_result = 'blocked') AS field_goal_blocked_candidates")
        if "extra_point_result" in columns:
            expressions.append("COUNT(*) FILTER (WHERE extra_point_result = 'blocked') AS extra_point_blocked_candidates")
        query = f"""SELECT {', '.join(expressions)}
          FROM read_parquet(?)
          WHERE season = 2025 AND week BETWEEN 1 AND 18
            AND game_id IS NOT NULL AND defteam IS NOT NULL AND posteam IS NOT NULL"""
        values = con.execute(query, [source]).fetchone()
        names = [col[0] for col in con.description]
    except Exception as exc:
        sys.exit("Blocked-kick coverage audit failed: " + str(exc))
    print(json.dumps({
        "scope": "2025 regular season",
        "field_coverage": {"present": present, "missing": missing},
        "candidate_counts": dict(zip(names, values)),
        "warnings": [
            "Blocked-kick flags may require review of event descriptions and attribution.",
            "ESPN points allowed cannot be inferred safely from opponent final score alone.",
            "No fantasy points, rankings, projections, model weights or output files."
        ]
    }, indent=2))

if __name__ == "__main__":
    main()
