#!/usr/bin/env python3
"""Read-only 2025 D/ST event-attribution diagnostic (not ESPN fantasy scoring).

Requires DuckDB. Outputs JSON to stdout. Does not write repository files.
Checks team attribution of interceptions, lost fumbles, touchdowns and scoring plays
in 2025 regular-season nflverse play-by-play data.
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
        needed = {"season", "week", "game_id", "posteam", "defteam", "interception", "fumble_lost", "fumble_recovery_1_team", "fumble_recovery_2_team", "touchdown", "td_team", "safety", "return_touchdown"}
        missing = sorted(needed - columns)
        if missing:
            sys.exit("Missing required columns: " + ", ".join(missing))
        sql = """
        SELECT
          COUNT(DISTINCT game_id) AS games,
          SUM(CASE WHEN interception = 1 THEN 1 ELSE 0 END) AS interceptions,
          SUM(CASE WHEN fumble_lost = 1 THEN 1 ELSE 0 END) AS fumbles_lost,
          SUM(CASE WHEN fumble_lost = 1 AND (fumble_recovery_1_team = defteam OR fumble_recovery_2_team = defteam) THEN 1 ELSE 0 END) AS lost_fumbles_with_defense_recovery_team,
          SUM(CASE WHEN fumble_lost = 1 AND NOT (COALESCE(fumble_recovery_1_team = defteam, FALSE) OR COALESCE(fumble_recovery_2_team = defteam, FALSE)) THEN 1 ELSE 0 END) AS lost_fumbles_without_matched_defense_recovery,
          SUM(CASE WHEN touchdown = 1 AND td_team = defteam THEN 1 ELSE 0 END) AS touchdown_credited_to_defteam,
          SUM(CASE WHEN touchdown = 1 AND td_team = posteam THEN 1 ELSE 0 END) AS touchdown_credited_to_posteam,
          SUM(CASE WHEN touchdown = 1 AND (td_team IS NULL OR td_team NOT IN (posteam, defteam)) THEN 1 ELSE 0 END) AS touchdown_team_unresolved,
          SUM(CASE WHEN safety = 1 THEN 1 ELSE 0 END) AS safety_plays,
          SUM(CASE WHEN return_touchdown = 1 THEN 1 ELSE 0 END) AS return_touchdown_plays
        FROM read_parquet(?)
        WHERE season = 2025 AND week BETWEEN 1 AND 18
          AND posteam IS NOT NULL AND defteam IS NOT NULL
        """
        values = con.execute(sql, [source]).fetchone()
        names = [x[0] for x in con.description]
    except Exception as exc:
        sys.exit("D/ST attribution audit failed: " + str(exc))
    print(json.dumps({
        "season": 2025, "scope": "regular_season_only",
        "diagnostics": dict(zip(names, values)),
        "interpretation": [
            "Counts are raw play-level candidates, not verified ESPN D/ST totals.",
            "td_team=defteam is not sufficient to capture all special-teams touchdowns.",
            "Safety attribution and ESPN points-allowed tiers need independent validation.",
            "No fantasy points, rankings, or model inputs were changed."
        ]
    }, indent=2))

if __name__ == "__main__":
    main()
