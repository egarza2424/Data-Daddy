#!/usr/bin/env python3
"""Read-only 2025 ESPN D/ST points-allowed input audit.

Examines nflverse scoring-event fields and score deltas; does NOT assign ESPN
points-allowed totals, fantasy scores, or modify repository files.
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
        fields = ["season", "week", "game_id", "play_id", "posteam", "defteam",
                  "home_team", "away_team", "home_score", "away_score",
                  "total_home_score", "total_away_score", "posteam_score",
                  "defteam_score", "posteam_score_post", "defteam_score_post",
                  "score_differential", "score_differential_post",
                  "touchdown", "td_team", "safety", "field_goal_result",
                  "extra_point_result", "two_point_conv_result",
                  "play_type", "desc", "return_touchdown"]
        present = [f for f in fields if f in cols]
        missing = [f for f in fields if f not in cols]
        required = {"season", "week", "game_id", "play_id", "posteam", "defteam"}
        if not required.issubset(cols):
            sys.exit("Missing essential fields: " + ", ".join(sorted(required - cols)))
        games = con.execute("""
            SELECT COUNT(DISTINCT game_id),
                   COUNT(DISTINCT game_id || ':' || defteam)
            FROM read_parquet(?)
            WHERE season = 2025 AND week BETWEEN 1 AND 18
              AND game_id IS NOT NULL AND defteam IS NOT NULL
        """, [source]).fetchone()
        score_fields = ["total_home_score", "total_away_score", "home_score", "away_score"]
        available_scores = [f for f in score_fields if f in cols]
        counts = {}
        for field in available_scores:
            counts[field] = con.execute(f"""
                SELECT COUNT(*) FILTER (WHERE {field} IS NULL),
                       COUNT(DISTINCT game_id) FILTER (WHERE {field} IS NOT NULL)
                FROM read_parquet(?)
                WHERE season = 2025 AND week BETWEEN 1 AND 18
            """, [source]).fetchone()
    except Exception as exc:
        sys.exit("Points-allowed input audit failed: " + str(exc))
    print(json.dumps({
        "season": 2025,
        "scope": "regular season",
        "games": games[0],
        "defensive_team_games": games[1],
        "field_coverage": {"present": present, "missing": missing},
        "score_field_null_rows_and_game_coverage": {
            k: {"null_play_rows": v[0], "games_with_values": v[1]}
            for k, v in counts.items()
        },
        "next_validation": [
            "Identify scoring team and points from play-level score changes.",
            "Exclude opponent defensive/special-teams scores from ESPN D/ST points allowed where required.",
            "Verify conversion, safety and return-play edge cases against ESPN.",
            "Compare resulting team-game totals to an independent ESPN reference."
        ],
        "warnings": [
            "Score-field presence does not establish correct ESPN points-allowed attribution.",
            "No points-allowed tiers or fantasy points are calculated.",
            "No files, rankings, projections, or model weights are changed."
        ]
    }, indent=2))

if __name__ == "__main__":
    main()
