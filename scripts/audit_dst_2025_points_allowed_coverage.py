#!/usr/bin/env python3
"""Read-only 2025 D/ST points-allowed coverage and scoring-mechanism audit."""
import duckdb,collections,json,sys
src=sys.argv[1] if len(sys.argv)>1 else "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_2025.parquet"
db=duckdb.connect()
q="""
WITH p AS (
 SELECT game_id,week,play_id,home_team,away_team,posteam,defteam,play_type,
 total_home_score hs,total_away_score aw,
 LAG(total_home_score) OVER(PARTITION BY game_id ORDER BY play_id) ph,
 LAG(total_away_score) OVER(PARTITION BY game_id ORDER BY play_id) pa
 FROM read_parquet(?) WHERE season=2025 AND week BETWEEN 1 AND 18
 AND game_id IS NOT NULL AND play_id IS NOT NULL
 AND COALESCE(play_type,'') <> 'GAME'
 AND (posteam IS NOT NULL OR defteam IS NOT NULL)
)
SELECT game_id,week,home_team,away_team,posteam,defteam,play_type,
 CASE WHEN hs>ph THEN home_team WHEN aw>pa THEN away_team END scorer,
 GREATEST(COALESCE(hs-ph,0),COALESCE(aw-pa,0)) points
FROM p
"""
rows=db.execute(q,[src]).fetchall()
all_games=set(); scores=collections.defaultdict(lambda:collections.Counter())
for game,week,home,away,off,defteam,typ,scorer,pts in rows:
 for defense in (home,away):
  if defense:all_games.add((week,game,defense))
 if not scorer or not pts:continue
 defense=away if scorer==home else home
 key=(week,game,defense)
 scores[key]["total"]+=int(pts)
 relation="possession" if scorer==off else ("defending" if scorer==defteam else "unattributed")
 scores[key][relation]+=int(pts)
 scores[key]["type_"+str(typ)]+=int(pts)
zero=sorted(all_games-set(scores))
non_scrimmage=[{"week":w,"game_id":g,"defense":d,"total":c["total"],"possession":c["possession"],
"kickoff":c["type_kickoff"],"punt":c["type_punt"],"field_goal":c["type_field_goal"],
"extra_point":c["type_extra_point"]} for (w,g,d),c in sorted(scores.items())
if any(c["type_"+t] for t in ("kickoff","punt","field_goal","extra_point"))]
print(json.dumps({"all_team_games":len(all_games),"scoring_team_games":len(scores),
"zero_point_team_games":[{"week":w,"game_id":g,"defense":d} for w,g,d in zero],
"non_scrimmage_scoring_team_games":non_scrimmage[:35],
"non_scrimmage_scoring_team_games_total":len(non_scrimmage),
"warning":"Scoring play type alone does not settle ESPN points-allowed eligibility; review cases before applying scoring tiers.",
"changes":"Read-only; no live website, rankings, projections, or model weights changed."},indent=2))
