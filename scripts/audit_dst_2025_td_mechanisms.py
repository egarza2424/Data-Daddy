#!/usr/bin/env python3
"""Read-only classification of 2025 D/ST touchdown mechanisms."""
import duckdb,json,collections,sys
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
SELECT game_id,week,play_id,play_type,interception,fumble_lost,
 return_touchdown,LEFT(description,180) description
FROM p WHERE (hs-ph=6 AND home_team=defteam)
 OR (aw-pa=6 AND away_team=defteam)
ORDER BY week,game_id,play_id
"""
rows=con.execute(q,[src]).fetchall()
events=[]
for game,week,pid,typ,interception,fumble,ret,description in rows:
 d=(description or "").upper()
 if typ in ("pass","run"):
  mechanism="interception_return" if interception==1 else ("fumble_return" if fumble==1 else "other_scrimmage")
 elif typ=="punt":
  mechanism="blocked_punt_td" if "BLOCKED" in d else "punt_return_or_recovery_td"
 elif typ=="field_goal":
  mechanism="blocked_field_goal_td" if "BLOCKED" in d else "other_field_goal"
 elif typ=="kickoff":
  mechanism="kickoff_return_or_recovery_td"
 else:mechanism="unclassified"
 events.append({"game_id":game,"week":week,"play_id":pid,"play_type":typ,"mechanism":mechanism,"description":description})
counts=dict(collections.Counter(e["mechanism"] for e in events))
print(json.dumps({"total":len(events),"mechanism_counts":counts,
"needs_review":[e for e in events if e["mechanism"] in ("other_scrimmage","other_field_goal","unclassified")],
"notes":["Provisional classification from flags and play descriptions; ESPN credit not independently validated.",
"No fantasy points, rankings, projections, website, or model weights changed."]},indent=2))
