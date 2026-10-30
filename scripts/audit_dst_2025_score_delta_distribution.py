#!/usr/bin/env python3
"""Read-only 2025 scoring-delta distribution, excluding GAME summary rows."""
import duckdb, json, sys
src=sys.argv[1] if len(sys.argv)>1 else "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_2025.parquet"
con=duckdb.connect()
query="""
WITH p AS (
 SELECT game_id,play_id,play_type,posteam,defteam,
 total_home_score h,total_away_score a,
 LAG(total_home_score) OVER(PARTITION BY game_id ORDER BY play_id) ph,
 LAG(total_away_score) OVER(PARTITION BY game_id ORDER BY play_id) pa
 FROM read_parquet(?)
 WHERE season=2025 AND week BETWEEN 1 AND 18
 AND game_id IS NOT NULL AND play_id IS NOT NULL
 AND COALESCE(play_type,'') <> 'GAME'
 AND (posteam IS NOT NULL OR defteam IS NOT NULL)
)
SELECT COALESCE(h-ph,0) dh, COALESCE(a-pa,0) da, COUNT(*) n
FROM p WHERE h>ph OR a>pa OR h<ph OR a<pa
GROUP BY 1,2 ORDER BY n DESC,dh,da
"""
try:
 rows=con.execute(query,[src]).fetchall()
except Exception as exc:
 sys.exit("Score-delta distribution audit failed: "+str(exc))
print(json.dumps({
 "scope":"2025 regular-season play rows excluding GAME summaries",
 "delta_distribution":[{"home_delta":h,"away_delta":a,"rows":n} for h,a,n in rows],
 "total_changed_rows":sum(n for _,_,n in rows),
 "caution":"Score changes may be on subsequent rows; validate against official game scoring summaries before ESPN D/ST points allowed.",
 "changes":"No fantasy points, website, rankings, projections, or model weights changed."
},indent=2))
