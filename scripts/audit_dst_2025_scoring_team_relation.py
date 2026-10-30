#!/usr/bin/env python3
"""Read-only diagnostic of 2025 nflverse scoring event attribution.

Score deltas are attached to rows where score changes become visible. Reports
scoring team vs possession team and sample events, not ESPN fantasy scoring.
"""
import json,sys,duckdb
src=sys.argv[1] if len(sys.argv)>1 else "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_2025.parquet"
con=duckdb.connect()
sql="""
WITH plays AS (
 SELECT game_id,week,play_id,home_team,away_team,posteam,defteam,td_team,
 play_type,"desc" AS description,interception,fumble_lost,return_touchdown,
 total_home_score AS hs,total_away_score AS ascore,
 LAG(total_home_score) OVER(PARTITION BY game_id ORDER BY play_id) AS prev_h,
 LAG(total_away_score) OVER(PARTITION BY game_id ORDER BY play_id) AS prev_a
 FROM read_parquet(?)
 WHERE season=2025 AND week BETWEEN 1 AND 18 AND game_id IS NOT NULL
 AND play_id IS NOT NULL AND COALESCE(play_type,'') <> 'GAME'
 AND (posteam IS NOT NULL OR defteam IS NOT NULL)
), changes AS (
 SELECT *, hs-prev_h AS hd, ascore-prev_a AS ad
 FROM plays
)
SELECT game_id,week,play_id,
 CASE WHEN hd>0 THEN home_team WHEN ad>0 THEN away_team ELSE NULL END scoring_team,
 GREATEST(COALESCE(hd,0),COALESCE(ad,0)) AS points,
 posteam,defteam,td_team,play_type,interception,fumble_lost,
 return_touchdown,LEFT(description,140) AS description
FROM changes WHERE hd>0 OR ad>0
ORDER BY game_id,play_id
"""
try:
 rows=con.execute(sql,[src]).fetchall()
except Exception as exc:
 sys.exit("Event attribution audit failed: "+str(exc))
names=[c[0] for c in con.description]
events=[dict(zip(names,row)) for row in rows]
groups={}
for e in events:
 relation="posteam" if e["scoring_team"]==e["posteam"] else ("defteam" if e["scoring_team"]==e["defteam"] else "neither_or_unknown")
 key=f"{e['points']}pt_{relation}"
 groups[key]=groups.get(key,0)+1
ambiguous=[e for e in events if e["scoring_team"] not in (e["posteam"],e["defteam"])]
print(json.dumps({
 "scoring_changes":len(events),
 "by_points_and_scoring_team_relation":groups,
 "unattributed_count":len(ambiguous),
 "unattributed_examples":ambiguous[:12],
 "warnings":["Scoring change may appear on a subsequent play; relation to posteam is not verified event attribution.",
 "No ESPN points-allowed totals or fantasy scores calculated.",
 "No live website, rankings, projections, or model changes."]
},indent=2))
