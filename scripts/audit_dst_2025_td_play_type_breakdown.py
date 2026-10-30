#!/usr/bin/env python3
"""Read-only classification of 2025 touchdowns credited to defteam."""
import duckdb,json,sys,collections
src=sys.argv[1] if len(sys.argv)>1 else "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_2025.parquet"
con=duckdb.connect()
q="""
WITH p AS (
 SELECT game_id,week,play_id,home_team,away_team,posteam,defteam,
 play_type,td_team,interception,fumble_lost,return_touchdown,"desc" description,
 total_home_score hs,total_away_score aw,
 LAG(total_home_score) OVER(PARTITION BY game_id ORDER BY play_id) ph,
 LAG(total_away_score) OVER(PARTITION BY game_id ORDER BY play_id) pa
 FROM read_parquet(?)
 WHERE season=2025 AND week BETWEEN 1 AND 18 AND game_id IS NOT NULL
 AND play_id IS NOT NULL AND COALESCE(play_type,'') <> 'GAME'
 AND (posteam IS NOT NULL OR defteam IS NOT NULL)
)
SELECT game_id,week,play_id,play_type,posteam,defteam,td_team,
 interception,fumble_lost,return_touchdown,LEFT(description,160)
FROM p WHERE (hs-ph=6 AND home_team=defteam)
 OR (aw-pa=6 AND away_team=defteam)
ORDER BY week,game_id,play_id
"""
try: rows=con.execute(q,[src]).fetchall()
except Exception as e:sys.exit("TD classification failed: "+str(e))
names=["game_id","week","play_id","play_type","posteam","defteam","td_team","interception","fumble_lost","return_touchdown","description"]
events=[dict(zip(names,r)) for r in rows]
groups=collections.Counter(e["play_type"] or "missing" for e in events)
other=[e for e in events if e["play_type"] not in ("pass","run","punt","kickoff","field_goal","extra_point")]
print(json.dumps({"defteam_six_point_events":len(events),
"by_play_type":dict(groups),"other_play_type_events":other,
"caution":"Play type provides a provisional grouping, not independently verified ESPN D/ST touchdown credit.",
"changes":"No live website, fantasy scoring, rankings, projections, or model weights changed."},indent=2))
