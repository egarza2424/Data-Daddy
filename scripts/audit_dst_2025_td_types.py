#!/usr/bin/env python3
"""Read-only diagnostic of 2025 D/ST touchdown attribution.

Prints aggregate candidate counts by play type and touchdown team. This is NOT
ESPN fantasy scoring. No files, rankings, or model outputs are modified.
"""
import json
import sys
import duckdb

SOURCE = "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_2025.parquet"

def main():
    source = sys.argv[1] if len(sys.argv) > 1 else SOURCE
    con = duckdb.connect()
    try:
        result = con.execute("""
            SELECT COALESCE(play_type, 'UNKNOWN') AS category,
                   CASE WHEN td_team = defteam THEN 'defteam'
                        WHEN td_team = posteam THEN 'posteam'
                        ELSE 'other_or_missing' END AS td_attribution,
                   COUNT(*) AS plays,
                   SUM(CASE WHEN return_touchdown = 1 THEN 1 ELSE 0 END) AS return_flagged
            FROM read_parquet(?)
            WHERE season = 2025 AND week BETWEEN 1 AND 18
              AND touchdown = 1 AND posteam IS NOT NULL AND defteam IS NOT NULL
            GROUP BY 1,2 ORDER BY 1,2
        """, [source]).fetchall()
    except Exception as exc:
        sys.exit("Touchdown attribution query failed: " + str(exc))
    print(json.dumps({
        "season": 2025,
        "scope": "regular_season",
        "groups": [dict(zip(("play_type", "td_attribution", "plays", "return_flagged"), row)) for row in result],
        "warnings": [
            "play_type labels the original play and does not by itself identify the scoring unit.",
            "Do not sum return_flagged and plays: those populations overlap.",
            "ESPN D/ST credit must be verified independently, especially on blocked kicks and returns.",
            "No fantasy scores or model changes."
        ]
    }, indent=2))

if __name__ == "__main__":
    main()
