#!/usr/bin/env python3
"""Read-only 2025 D/ST score-change coverage diagnostic.

Checks score-delta reconstruction at game level and identifies suspicious
score transitions. Does not award ESPN points or write files.
"""
import json
import sys
import duckdb

SOURCE = "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_2025.parquet"

def main():
    source = sys.argv[1] if len(sys.argv) > 1 else SOURCE
    con = duckdb.connect()
    try:
        cols = {r[0] for r in con.execute("DESCRIBE SELECT * FROM read_parquet(?)", [source]).fetchall()}
        required = {"season", "week", "game_id", "play_id", "home_team",
                    "away_team", "total_home_score", "total_away_score"}
        missing = sorted(required - cols)
        if missing:
            sys.exit("Missing required fields: " + ", ".join(missing))
        rows = con.execute("""
          WITH ordered AS (
            SELECT game_id, week, play_id, home_team, away_team,
                   total_home_score AS home_pts,
                   total_away_score AS away_pts,
                   LAG(total_home_score, 1, 0) OVER
                     (PARTITION BY game_id ORDER BY play_id) AS prior_home,
                   LAG(total_away_score, 1, 0) OVER
                     (PARTITION BY game_id ORDER BY play_id) AS prior_away
            FROM read_parquet(?)
            WHERE season = 2025 AND week BETWEEN 1 AND 18
              AND game_id IS NOT NULL AND play_id IS NOT NULL
          )
          SELECT game_id, MAX(week) AS week,
                 MAX(home_team) AS home_team, MAX(away_team) AS away_team,
                 COUNT(*) AS plays,
                 SUM(CASE WHEN home_pts IS NULL OR away_pts IS NULL
                           THEN 1 ELSE 0 END) AS missing_score_rows,
                 SUM(CASE WHEN home_pts - prior_home > 0
                           THEN home_pts - prior_home ELSE 0 END) AS home_positive_deltas,
                 SUM(CASE WHEN away_pts - prior_away > 0
                           THEN away_pts - prior_away ELSE 0 END) AS away_positive_deltas,
                 SUM(CASE WHEN home_pts < prior_home OR away_pts < prior_away
                           THEN 1 ELSE 0 END) AS decreasing_score_rows,
                 SUM(CASE WHEN home_pts - prior_home > 8 OR away_pts - prior_away > 8
                           THEN 1 ELSE 0 END) AS large_score_jump_rows
          FROM ordered GROUP BY game_id ORDER BY game_id
        """, [source]).fetchall()
    except Exception as exc:
        sys.exit("Score delta audit failed: " + str(exc))
    names = ["game_id", "week", "home_team", "away_team", "plays",
             "missing_score_rows", "home_positive_deltas", "away_positive_deltas",
             "decreasing_score_rows", "large_score_jump_rows"]
    print(json.dumps({
        "scope": "2025 regular season",
        "games": len(rows),
        "total_missing_score_rows": sum(r[5] for r in rows),
        "total_decreasing_score_rows": sum(r[8] for r in rows),
        "total_large_score_jump_rows": sum(r[9] for r in rows),
        "sample_games": [dict(zip(names, row)) for row in rows[:5]],
        "warnings": [
            "This checks score reconstruction only, not ESPN D/ST points allowed.",
            "Scoring attribution and defensive/special-teams exclusions remain unverified.",
            "No fantasy scores, rankings, projections, model changes, or files written."
        ]
    }, indent=2))

if __name__ == "__main__":
    main()
