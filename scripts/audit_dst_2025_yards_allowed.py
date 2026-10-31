#!/usr/bin/env python3
"""Read-only audit of 2025 offensive yards allowed by D/ST, not fantasy points."""
import collections,duckdb,json,sys
src=sys.argv[1] if len(sys.argv)>1 else "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_2025.parquet"
db=duckdb.connect()
rows=db.execute("""SELECT game_id,week,home_team,away_team,posteam,defteam,play_type,yards_gained,sack
FROM read_parquet(?) WHERE season=2025 AND week BETWEEN 1 AND 18
AND game_id IS NOT NULL AND play_id IS NOT NULL
AND COALESCE(play_type,'') <> 'GAME'
ORDER BY game_id,play_id""",[src]).fetchall()
data=collections.defaultdict(lambda:collections.Counter())
for game,week,home,away,off,defteam,typ,yards,sack in rows:
 for team in (home,away):data[(week,game,team)]
 if not off or not defteam:continue
 if typ in ("run","pass"):
  data[(week,game,defteam)]["scrimmage_plays"]+=1
  if yards is not None:data[(week,game,defteam)]["candidate_offensive_yards_allowed"]+=yards
  else:data[(week,game,defteam)]["missing_yards_plays"]+=1
  if sack==1:data[(week,game,defteam)]["sacks"]+=1
 if typ in ("punt","kickoff","field_goal","extra_point"):
  data[(week,game,defteam)]["excluded_special_teams_plays"]+=1
samples=[{"week":week,"game_id":game,"defense":team,**dict(c)} for (week,game,team),c in sorted(data.items())]
print(json.dumps({"team_games":len(samples),"totals":{"candidate_offensive_yards_allowed":sum(x["candidate_offensive_yards_allowed"] for x in data.values()),"scrimmage_plays":sum(x["scrimmage_plays"] for x in data.values()),"missing_yards_plays":sum(x["missing_yards_plays"] for x in data.values())},"sample_team_games":samples[:16],"highest_yards_allowed":sorted(samples,key=lambda x:x.get("candidate_offensive_yards_allowed",0),reverse=True)[:10],"cautions":["This is an audit, not ESPN-validated total offensive yards or yards-allowed fantasy points.","Compare to official team box scores before choosing scoring tiers; sack and penalty attribution may differ.","No production data or model changes."]},indent=2))
