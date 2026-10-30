#!/usr/bin/env python3
"""Read-only diagnostic of score decreases in 2025 nflverse play-by-play."""
import json
import sys
import duckdb

SOURCE = "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_2025.parquet"
con = duckdb.connect()
source = sys.argv[1] if len(sys.argv) > 1 else SOURCE
try:
    rows = con.execute("""
      WITH ordered AS (
        SELECT game_id, week, play_id, qtr, "desc",
               total_home_score AS home_score_value,
               total_away_score AS away_score_value,
               LAG(total_home_score) OVER (PARTITION BY game_id ORDER BY play_id) AS prior_home,
               LAG(total_away_score) OVER (PARTITION BY game_id ORDER BY play_id) AS prior_away
        FROM read_parquet(?)
        WHERE season = 2025 AND week BETWEEN 1 AND 18 AND game_id IS NOT NULL
          AND play_id IS NOT NULL
      )
      SELECT game_id, week, play_id, qtr, prior_home, home_score_value,
             prior_away, away_score_value, LEFT("desc", 180) AS description
      FROM ordered
      WHERE home_score_value < prior_home OR away_score_value < prior_away
      ORDER BY week, game_id, play_id
      LIMIT 15
    """, [source]).fetchall()
    counts = con.execute("""
      WITH ordered AS (
        SELECT game_id, play_id, total_home_score, total_away_score,
          LAG(total_home_score) OVER (PARTITION BY game_id ORDER BY play_id) AS prior_home,
          LAG(total_away_score) OVER (PARTITION BY game_id ORDER BY play_id) AS prior_away
        FROM read_parquet(?)
        WHERE season = 2025 AND week BETWEEN 1 AND 18 AND game_id IS NOT NULL
          AND play_id IS NOT NULL
      )
      SELECT COUNT(*) FILTER (WHERE total_home_score < prior_home
                             OR total_away_score < prior_away) AS decrease_rows,
             COUNT(DISTINCT game_id) FILTER (WHERE total_home_score < prior_home
                             OR total_away_score < prior_away) AS affected_games
      FROM ordered
    """, [source]).fetchone()
except Exception as exc:
    sys.exit("Score decrease investigation failed: " + str(exc))
names = ["game_id", "week", "play_id", "quarter", "prior_home", "current_home",
         "prior_away", "current_away", "description"]
print(json.dumps({
    "decrease_rows": counts[0], "affected_games": counts[1],
    "examples": [dict(zip(names, row)) for row in rows],
    "note": "Diagnostic only. A decrease may reflect data semantics, corrections, or ordering; no scoring conclusions yet."
}, indent=2))
