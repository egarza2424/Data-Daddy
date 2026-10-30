#!/usr/bin/env python3
"""Read-only comparison of nflverse scoreboard field monotonicity, 2025 REG."""
import duckdb, json, sys
src=sys.argv[1] if len(sys.argv)>1 else "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_2025.parquet"
con=duckdb.connect()
cols={r[0] for r in con.execute("DESCRIBE SELECT * FROM read_parquet(?)",[src]).fetchall()}
pairs=[(a,b) for a,b in [("total_home_score","total_away_score"),("home_score","away_score")] if a in cols and b in cols]
result={}
for home,away in pairs:
    q=f"""
    WITH s AS (
      SELECT game_id,play_id,{home} h,{away} a,
      LAG({home}) OVER (PARTITION BY game_id ORDER BY play_id) ph,
      LAG({away}) OVER (PARTITION BY game_id ORDER BY play_id) pa
      FROM read_parquet(?) WHERE season=2025 AND week BETWEEN 1 AND 18
      AND game_id IS NOT NULL AND play_id IS NOT NULL
    )
    SELECT COUNT(*) FILTER(WHERE h<ph OR a<pa),
           COUNT(DISTINCT game_id) FILTER(WHERE h<ph OR a<pa),
           COUNT(*) FILTER(WHERE h IS NULL OR a IS NULL)
    FROM s"""
    r=con.execute(q,[src]).fetchone()
    result[f"{home}/{away}"]={"decrease_rows":r[0],"affected_games":r[1],"null_rows":r[2]}
print(json.dumps({"field_comparison":result,"note":"Score fields are not yet validated as ESPN D/ST points allowed. No files or model outputs changed."},indent=2))
