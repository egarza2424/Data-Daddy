#!/usr/bin/env python3
"""Read-only 2025 D/ST game coverage audit: regular season vs playoffs and duplicates."""
import json
import sys
import duckdb

source = sys.argv[1] if len(sys.argv) > 1 else "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_2025.parquet"
con = duckdb.connect()
try:
    rows = con.execute("""
        SELECT CASE WHEN week BETWEEN 1 AND 18 THEN 'REG' WHEN week > 18 THEN 'POST' ELSE 'UNKNOWN' END AS game_type_label,
               COUNT(DISTINCT game_id) AS games,
               COUNT(DISTINCT game_id || ':' || defteam) AS defense_team_games,
               COUNT(DISTINCT defteam) AS teams,
               COUNT(*) AS play_rows
        FROM read_parquet(?)
        WHERE season = 2025 AND game_id IS NOT NULL AND defteam IS NOT NULL
        GROUP BY 1 ORDER BY 1
    """, [source]).fetchall()
    duplicates = con.execute("""
        SELECT game_id, defteam, COUNT(DISTINCT week) AS distinct_weeks,
               COUNT(DISTINCT CASE WHEN week BETWEEN 1 AND 18 THEN 'REG' WHEN week > 18 THEN 'POST' ELSE 'UNKNOWN' END) AS distinct_game_types
        FROM read_parquet(?)
        WHERE season = 2025 AND game_id IS NOT NULL AND defteam IS NOT NULL
        GROUP BY 1,2
        HAVING COUNT(DISTINCT week) > 1 OR COUNT(DISTINCT CASE WHEN week BETWEEN 1 AND 18 THEN 'REG' WHEN week > 18 THEN 'POST' ELSE 'UNKNOWN' END) > 1
        ORDER BY game_id, defteam
    """, [source]).fetchall()
except Exception as exc:
    sys.exit(f"Coverage query failed: {exc}")
print(json.dumps({
    "season": 2025,
    "by_game_type": [
        dict(zip(["game_type", "games", "defense_team_games", "teams", "play_rows"], row))
        for row in rows
    ],
    "conflicting_game_team_identifiers": [
        dict(zip(["game_id", "defteam", "distinct_weeks", "distinct_game_types"], row))
        for row in duplicates[:25]
    ],
    "notes": [
        "This counts unique game/team IDs, not raw plays.",
        "Compare REG against 272 games / 544 team-games; exclude postseason from regular-season backtests.",
        "No fantasy scoring, model changes, or output files."
    ]
}, indent=2))
