#!/usr/bin/env python3
"""Read-only 2025 nflverse D/ST special-teams touchdown event review.

Outputs candidate game/play details for manual ESPN scoring verification.
No files are written; no fantasy points or rankings are calculated.
"""
import json
import sys
import duckdb

SOURCE = "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_2025.parquet"

def main():
    source = sys.argv[1] if len(sys.argv) > 1 else SOURCE
    con = duckdb.connect()
    required = ["game_id", "week", "posteam", "defteam", "td_team",
                "play_type", "return_touchdown", "desc", "play_id", "touchdown", "season"]
    try:
        available = {row[0] for row in con.execute("DESCRIBE SELECT * FROM read_parquet(?)", [source]).fetchall()}
        missing = sorted(set(required) - available)
        if missing:
            sys.exit("Missing columns: " + ", ".join(missing))
        rows = con.execute("""
            SELECT game_id, week, play_id, play_type, posteam, defteam, td_team,
                   return_touchdown, "desc"
            FROM read_parquet(?)
            WHERE season = 2025 AND week BETWEEN 1 AND 18 AND touchdown = 1
              AND play_type IN ('kickoff', 'punt', 'field_goal')
            ORDER BY week, game_id, play_id
        """, [source]).fetchall()
    except Exception as exc:
        sys.exit("Special-teams audit failed: " + str(exc))
    fields = ["game_id", "week", "play_id", "play_type", "posteam",
              "defteam", "td_team", "return_touchdown", "description"]
    print(json.dumps({
        "scope": "2025 regular-season candidate special-teams touchdown plays",
        "total_candidate_plays": len(rows),
        "plays": [dict(zip(fields, row)) for row in rows],
        "cautions": [
            "These are candidate plays, not confirmed ESPN D/ST credits.",
            "Review the description and scoring unit for each event.",
            "Do not sum return_touchdown and touchdown flags.",
            "No website, projections, rankings, or model changes."
        ]
    }, indent=2))

if __name__ == "__main__":
    main()
