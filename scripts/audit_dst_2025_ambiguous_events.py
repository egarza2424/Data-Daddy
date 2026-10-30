#!/usr/bin/env python3
"""Read-only review of ambiguous 2025 D/ST fumbles and touchdowns.

Prints aggregate counts only; no fantasy points, files, or model changes.
"""
import json
import sys
import duckdb

source = sys.argv[1] if len(sys.argv) > 1 else "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_2025.parquet"
con = duckdb.connect()
try:
    columns = {row[0] for row in con.execute("DESCRIBE SELECT * FROM read_parquet(?)", [source]).fetchall()}
    required = {"season", "week", "game_id", "posteam", "defteam", "fumble_lost",
                "fumble_recovery_1_team", "fumble_recovery_2_team", "touchdown",
                "td_team", "return_touchdown", "play_type"}
    missing = sorted(required - columns)
    if missing:
        sys.exit("Missing fields: " + ", ".join(missing))
    result = con.execute("""
        WITH plays AS (
          SELECT *,
            COALESCE(fumble_recovery_1_team = defteam, FALSE)
            OR COALESCE(fumble_recovery_2_team = defteam, FALSE) AS recovered_by_defense
          FROM read_parquet(?)
          WHERE season = 2025 AND week BETWEEN 1 AND 18
            AND posteam IS NOT NULL AND defteam IS NOT NULL
        )
        SELECT
          COUNT(*) FILTER (WHERE fumble_lost = 1 AND NOT recovered_by_defense) AS unmatched_lost_fumbles,
          COUNT(*) FILTER (WHERE fumble_lost = 1 AND NOT recovered_by_defense
                            AND fumble_recovery_1_team IS NULL AND fumble_recovery_2_team IS NULL) AS missing_recovery_team,
          COUNT(*) FILTER (WHERE fumble_lost = 1 AND NOT recovered_by_defense
                            AND (fumble_recovery_1_team = posteam OR fumble_recovery_2_team = posteam)) AS offense_recovery_team_listed,
          COUNT(*) FILTER (WHERE touchdown = 1 AND td_team = defteam) AS defteam_touchdown_candidates,
          COUNT(*) FILTER (WHERE touchdown = 1 AND td_team = defteam AND return_touchdown = 1) AS defteam_return_touchdown_overlap,
          COUNT(*) FILTER (WHERE touchdown = 1 AND return_touchdown = 1 AND td_team <> defteam) AS other_return_touchdowns
        FROM plays
    """, [source]).fetchone()
    names = [item[0] for item in con.description]
    td_types = con.execute("""
        SELECT COALESCE(play_type, 'UNKNOWN') AS play_category, COUNT(*) AS plays
        FROM read_parquet(?)
        WHERE season = 2025 AND week BETWEEN 1 AND 18
          AND touchdown = 1 AND td_team = defteam
          AND posteam IS NOT NULL AND defteam IS NOT NULL
        GROUP BY 1 ORDER BY 2 DESC
    """, [source]).fetchall()
except Exception as exc:
    sys.exit("Attribution check failed: " + str(exc))
print(json.dumps({
    "scope": "2025 regular season",
    "counts": dict(zip(names, result)),
    "defteam_touchdown_play_types": [{"play_type": name, "plays": count} for name, count in td_types],
    "cautions": [
        "Fumble and touchdown flags require ESPN event-credit verification.",
        "Special-teams touchdowns may have no conventional offensive possession team.",
        "No fantasy scores, rankings, or projections were calculated."
    ]
}, indent=2))
