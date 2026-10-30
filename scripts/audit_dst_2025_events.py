#!/usr/bin/env python3
"""Read-only 2025 nflverse D/ST team-game event extraction (NOT ESPN fantasy scoring).

Run: python scripts/audit_dst_2025_events.py
Prints JSON summary; does not write repository files or change models.
Uses nflverse PBP 2025 parquet through DuckDB. Event totals are provisional.
"""
import json
import sys

URL = "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_2025.parquet"

def main():
    try:
        import duckdb
    except ImportError:
        sys.exit("Install DuckDB first: python -m pip install duckdb")
    con = duckdb.connect()
    source = sys.argv[1] if len(sys.argv) > 1 else URL
    try:
        con.execute("CREATE VIEW pbp AS SELECT * FROM read_parquet(?)", [source])
        cols = {r[0] for r in con.execute("DESCRIBE pbp").fetchall()}
        required = {"season", "week", "game_id", "defteam", "posteam", "sack", "interception", "fumble_lost", "safety"}
        missing = sorted(required - cols)
        if missing:
            sys.exit("Required columns missing: " + ", ".join(missing))
        rows = con.execute("""
            SELECT season, week, game_id, defteam AS team,
                   COUNT(*) FILTER (WHERE sack = 1) AS sacks,
                   COUNT(*) FILTER (WHERE interception = 1) AS interceptions,
                   COUNT(*) FILTER (WHERE fumble_lost = 1) AS opponent_fumbles_lost,
                   COUNT(*) FILTER (WHERE safety = 1) AS safeties
            FROM pbp
            WHERE season = 2025 AND defteam IS NOT NULL
              AND posteam IS NOT NULL AND defteam <> posteam
            GROUP BY 1,2,3,4
            ORDER BY week, game_id, team
        """).fetchall()
    except Exception as exc:
        sys.exit("Data read failed: " + str(exc))
    report = {
        "status": "provisional_event_counts_not_espn_scoring",
        "source": source,
        "season": 2025,
        "team_games": len(rows),
        "teams": sorted({r[3] for r in rows}),
        "sample_first_12": [
            dict(zip(("season", "week", "game_id", "team", "sacks",
                      "interceptions", "opponent_fumbles_lost", "safeties"), r))
            for r in rows[:12]
        ],
        "limitations": [
            "Fumbles lost are not yet verified as defense-credited recoveries.",
            "Defensive/special teams TDs, blocked kicks, and ESPN points allowed are not calculated.",
            "No fantasy points or rankings are calculated.",
            "Review team-game counts and event attribution before implementing scoring."
        ]
    }
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
