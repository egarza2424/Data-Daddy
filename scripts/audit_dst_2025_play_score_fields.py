#!/usr/bin/env python3
"""Read-only diagnostic of nflverse 2025 play-level score fields.

Excludes non-play GAME rows and compares score changes across candidate
score fields. Does not calculate fantasy points or modify files.
"""
import duckdb, json, sys
src=sys.argv[1] if len(sys.argv)>1 else "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_2025.parquet"
con=duckdb.connect()
cols={r[0] for r in con.execute("DESCRIBE SELECT * FROM read_parquet(?)",[src]).fetchall()}
pairs=[("home_score","away_score"),("total_home_score","total_away_score")]
out={}
for home,away in pairs:
    if home not in cols or away not in cols:
        out[home+"/"+away]={"missing_fields":True}
        continue
    q=f"""
    WITH p AS (
      SELECT game_id,play_id,play_type,posteam,defteam,
        {home} h,{away} a,
        LAG({home}) OVER(PARTITION BY game_id ORDER BY play_id) ph,
        LAG({away}) OVER(PARTITION BY game_id ORDER BY play_id) pa
      FROM read_parquet(?)
      WHERE season=2025 AND week BETWEEN 1 AND 18
        AND game_id IS NOT NULL AND play_id IS NOT NULL
        AND COALESCE(play_type,'') <> 'GAME'
        AND (posteam IS NOT NULL OR defteam IS NOT NULL)
    )
    SELECT COUNT(*),
      COUNT(*) FILTER(WHERE h>ph OR a>pa),
      COUNT(*) FILTER(WHERE h<ph OR a<pa),
      COUNT(*) FILTER(WHERE h IS NULL OR a IS NULL),
      COUNT(DISTINCT game_id)
    FROM p"""
    r=con.execute(q,[src]).fetchone()
    out[home+"/"+away]=dict(zip(["play_rows","positive_change_rows","decrease_rows","null_rows","games"],r))
print(json.dumps({"candidate_field_comparison":out,
"interpretation":"Diagnostic only. Further validation against event-level scoring and ESPN is required.",
"changes":"No repository files, rankings, projections, fantasy scores or model weights changed."},indent=2))
