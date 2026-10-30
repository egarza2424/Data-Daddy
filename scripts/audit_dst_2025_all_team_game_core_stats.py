#!/usr/bin/env python3
"""Read-only 2025 D/ST team-game core stat aggregation diagnostic."""
import collections,duckdb,json,sys
src=sys.argv[1] if len(sys.argv)>1 else "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_2025.parquet"
db=duckdb.connect()
cols={r[0] for r in db.execute("DESCRIBE SELECT * FROM read_parquet(?)",[src]).fetchall()}
required={"game_id","week","home_team","away_team","defteam","play_id","sack","interception","fumble_lost"}
missing=sorted(required-cols)
if missing:sys.exit("Missing columns: "+", ".join(missing))
sql="""
SELECT game_id,week,home_team,away_team,defteam,play_id,
 COALESCE(sack,0),COALESCE(interception,0),COALESCE(fumble_lost,0)
FROM read_parquet(?)
WHERE season=2025 AND week BETWEEN 1 AND 18
 AND game_id IS NOT NULL AND play_id IS NOT NULL
 AND COALESCE(play_type,'') <> 'GAME'
"""
rows=db.execute(sql,[src]).fetchall()
teamgames=collections.defaultdict(lambda:collections.Counter())
for game,week,home,away,defteam,pid,sack,interception,fumble in rows:
 for team in (home,away):
  if team:teamgames[(week,game,team)]
 if defteam:
  c=teamgames[(week,game,defteam)]
  c["sacks"]+=int(sack==1)
  c["interceptions"]+=int(interception==1)
  c["opponent_fumbles_lost_candidate"]+=int(fumble==1)
totals=collections.Counter()
for c in teamgames.values():totals.update(c)
print(json.dumps({"team_games":len(teamgames),"totals":dict(totals),
"sample_team_games":[{"week":w,"game_id":g,"defense":d,**dict(c)} for (w,g,d),c in sorted(teamgames.items())[:12]],
"limitations":["Fumbles lost are candidates, not confirmed credited defensive recoveries.","Sacks may require checking fractional or team attribution against ESPN.","Blocked kicks and points allowed not yet included.","No files written and no live website, rankings, projections or weights changed."]},indent=2))
