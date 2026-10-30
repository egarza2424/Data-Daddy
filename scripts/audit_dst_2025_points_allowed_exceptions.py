#!/usr/bin/env python3
"""Read-only diagnostic of 2025 scoring events needing ESPN D/ST points-allowed review."""
import duckdb,collections,json,sys
src=sys.argv[1] if len(sys.argv)>1 else "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_2025.parquet"
db=duckdb.connect()
cols={r[0] for r in db.execute("DESCRIBE SELECT * FROM read_parquet(?)",[src]).fetchall()}
wanted=["game_id","week","play_id","home_team","away_team","posteam","defteam","play_type","desc","total_home_score","total_away_score"]
select=", ".join('"'+c+'"' if c in cols else 'NULL AS "'+c+'"' for c in wanted)
rows=db.execute(f"""SELECT {select} FROM read_parquet(?)
WHERE season=2025 AND week BETWEEN 1 AND 18 AND game_id IS NOT NULL
AND play_id IS NOT NULL AND COALESCE(play_type,'') <> 'GAME'
AND (posteam IS NOT NULL OR defteam IS NOT NULL)
ORDER BY game_id,play_id""",[src]).fetchall()
prev={}; categories=collections.Counter(); exceptions=[]
for game,week,pid,home,away,off,defteam,typ,desc,hs,aws in rows:
 if hs is None or aws is None:continue
 old=prev.get(game,(hs,aws));prev[game]=(hs,aws)
 dh=hs-old[0]; da=aws-old[1]
 if dh<=0 and da<=0:continue
 if dh>0 and da>0:continue
 scorer=home if dh>0 else away;points=int(max(dh,da))
 if scorer==defteam:
  category="defense_or_special_teams_score"
 elif typ in ("kickoff","punt"):
  category="kick_or_punt_return_score"
 elif scorer==off:
  category="offense_or_kicking_score"
 else:
  category="other_attribution"
 categories[category]+=1
 if category!="offense_or_kicking_score":
  exceptions.append({"game_id":game,"week":week,"play_id":pid,"scorer":scorer,"posteam":off,"defteam":defteam,"play_type":typ,"points":points,"category":category,"description":(desc or "")[:220]})
print(json.dumps({"scoring_event_categories":dict(categories),"exception_events":len(exceptions),
"exceptions":exceptions[:110],"truncated":len(exceptions)>110,
"notes":["Score changes can appear on subsequent rows; verify unusual cases before ESPN scoring.","This audit does not calculate fantasy points or change production data."]},indent=2))
