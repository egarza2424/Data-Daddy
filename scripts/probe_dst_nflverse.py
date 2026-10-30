#!/usr/bin/env python3
"""Read-only nflverse D/ST input coverage probe; no fantasy scores are computed.

Run: python scripts/probe_dst_nflverse.py
Downloads only 2025 play-by-play column metadata plus a small sample via DuckDB
if available; alternatively supply a local parquet path as first argument.
No repository files are written.
"""
import json
import sys

COLUMNS = {
    "identity": ["game_id", "season", "week", "posteam", "defteam", "home_team", "away_team"],
    "sacks": ["sack"],
    "interceptions": ["interception", "interception_player_id"],
    "fumbles": ["fumble", "fumble_lost", "fumble_recovery_1_team", "fumble_recovery_2_team"],
    "touchdowns": ["touchdown", "defensive_two_point_conv", "return_touchdown", "td_team"],
    "safeties": ["safety"],
    "blocks": ["blocked_player_id", "field_goal_result", "punt_blocked"],
    "returns": ["kickoff_returner_player_id", "punt_returner_player_id", "return_yards"],
    "points": ["total_home_score", "total_away_score", "home_score", "away_score"],
}
URL = "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_2025.parquet"

def main():
    try:
        import duckdb
    except ImportError:
        print("DuckDB not installed. Install with: python -m pip install duckdb")
        return 2
    source = sys.argv[1] if len(sys.argv) > 1 else URL
    con = duckdb.connect()
    try:
        rows = con.execute("DESCRIBE SELECT * FROM read_parquet(?)", [source]).fetchall()
    except Exception as exc:
        print(f"Could not read parquet schema: {exc}")
        return 1
    names = {row[0] for row in rows}
    result = {
        "source": source,
        "audit": "schema_only_no_scoring_or_writes",
        "categories": {
            group: {"present": [x for x in cols if x in names],
                    "missing": [x for x in cols if x not in names]}
            for group, cols in COLUMNS.items()
        },
        "caution": "Column presence does not verify ESPN scoring, attribution, or historical completeness."
    }
    print(json.dumps(result, indent=2))
    return 0

if __name__ == "__main__":
    sys.exit(main())
