#!/usr/bin/env python3
"""Read-only 2025 D/ST prototype: event totals, not final ESPN fantasy points."""
import collections,json,sys,duckdb
src=sys.argv[1] if len(sys.argv)>1 else "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_2025.parquet"
db=duckdb.connect()
q="""
WITH p AS (
 SELECT game_id,week,play_id,home_team,away_team,posteam,defteam,play_type,
 interception,fumble_lost,safety,defensive_two_point_conv,
 total_home_score h,total_away_score a,
 LAG(total_home_score) OVER(PARTITION BY game_id ORDER BY play_id) ph,
 LAG(total_away_score) OVER(PARTITION BY game_id ORDER BY play_id) pa
 FROM read_parquet(?)
 WHERE season=2025 AND week BETWEEN 1 AND 18 AND game_id IS NOT NULL
 AND play_id IS NOT NULL AND COALESCE(play_type,'') <> 'GAME'
 AND (posteam IS NOT NULL OR defteam IS NOT NULL)
)
SELECT game_id,week,defteam,play_type,interception,fumble_lost,safety,
 defensive_two_point_conv,
 CASE WHEN h>ph THEN home_team WHEN a>pa THEN away_team END scoring_team,
 GREATEST(COALESCE(h-ph,0),COALESCE(a-pa,0)) delta
FROM p WHERE h>ph OR a>pa
"""
rows=db.execute(q,[src]).fetchall()
out=collections.defaultdict(lambda:collections.Counter())
for game,week,defteam,typ,interception,fumble,safety,conv,scorer,delta in rows:
 if scorer!=defteam:continue
 key=(week,game,defteam)
 if delta==6:
  out[key]["defensive_td" if typ in ("pass","run") else "special_teams_td"]+=1
 elif delta==2:
  if safety==1:out[key]["safety"]+=1
  elif conv==1:out[key]["defensive_two_point_conversion"]+=1
  else:out[key]["unresolved_two_point"]+=1
totals=collections.Counter()
for counts in out.values():totals.update(counts)
print(json.dumps({"scope":"2025 regular-season scoring events credited to defteam",
"team_games_with_events":len(out),"totals":dict(totals),
"sample_team_games":[{"week":w,"game_id":g,"defense":d,**dict(v)} for (w,g,d),v in sorted(out.items())[:12]],
"limitations":["Not a complete ESPN D/ST score: sacks, interceptions, fumble recoveries, blocked kicks and points allowed still need validated aggregation.",
"Play-type touchdown classification is provisional.","No outputs saved; no live site, rankings, projections or model changes."]},indent=2))
