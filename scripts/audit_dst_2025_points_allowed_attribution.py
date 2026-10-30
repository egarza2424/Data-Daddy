#!/usr/bin/env python3
"""Read-only audit of 2025 opponent points allowed by offense versus D/ST scores."""
import duckdb,json,collections,sys
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
 CASE WHEN hs>ph THEN home_team WHEN aw>pa THEN away_team END scoring_team,
 GREATEST(COALESCE(hs-ph,0),COALESCE(aw-pa,0)) delta
FROM p WHERE hs>ph OR aw>pa
"""
rows=db.execute(q,[src]).fetchall()
teams=collections.defaultdict(lambda:collections.Counter())
ambiguous=[]
for game,week,home,away,off,defteam,typ,scorer,delta in rows:
 for defense in (home,away):
  if defense==scorer:continue
  c=teams[(week,game,defense)]
  c["opponent_score_all"]+=int(delta)
  if scorer==off:c["opponent_score_possession_team"]+=int(delta)
  elif scorer==defteam:c["opponent_score_defending_team"]+=int(delta)
  else:
   c["opponent_score_unattributed"]+=int(delta)
   if len(ambiguous)<12:ambiguous.append({"game_id":game,"play_type":typ,"points":delta})
examples=[{"week":w,"game_id":g,"defense":d,**dict(v)} for (w,g,d),v in sorted(teams.items()) if v["opponent_score_defending_team"]][:12]
print(json.dumps({"team_games_with_opponent_scores":len(teams),
"total_opponent_score":sum(c["opponent_score_all"] for c in teams.values()),
"total_possession_team_score":sum(c["opponent_score_possession_team"] for c in teams.values()),
"total_defending_team_score":sum(c["opponent_score_defending_team"] for c in teams.values()),
"defense_team_scoring_examples":examples,"unattributed_examples":ambiguous,
"caution":"Possession-team scoring is only a provisional points-allowed proxy. ESPN may handle safeties, kick returns, and two-point conversions differently; validate before fantasy scoring.",
"changes":"Read-only; no live site, rankings, projections or model weights changed."},indent=2))
