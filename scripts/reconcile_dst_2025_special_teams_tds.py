#!/usr/bin/env python3
"""Read-only reconciliation of special-teams TD counts between two 2025 audits."""
import duckdb,collections,json,sys
src=sys.argv[1] if len(sys.argv)>1 else "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_2025.parquet"
db=duckdb.connect()
rows=db.execute("""SELECT game_id,week,play_id,home_team,away_team,posteam,defteam,play_type,"desc",total_home_score,total_away_score
FROM read_parquet(?) WHERE season=2025 AND week BETWEEN 1 AND 18
AND game_id IS NOT NULL AND play_id IS NOT NULL
AND COALESCE(play_type,'') <> 'GAME' AND (posteam IS NOT NULL OR defteam IS NOT NULL)
ORDER BY game_id,play_id""",[src]).fetchall()
prev={};items=[]
for game,week,pid,home,away,off,defteam,typ,desc,hs,aws in rows:
 if hs is None or aws is None:continue
 old=prev.get(game,(hs,aws));prev[game]=(hs,aws)
 dh=hs-old[0];da=aws-old[1]
 if dh<=0 and da<=0:continue
 scorer=home if dh>0 else away;pts=max(dh,da)
 if pts!=6:continue
 if scorer==defteam and typ not in ("pass","run"):
  bucket="defteam_non_scrimmage"
 elif typ=="kickoff" and scorer==off:
  bucket="kickoff_return"
 else:continue
 items.append({"game_id":game,"week":week,"play_id":pid,"scorer":scorer,"posteam":off,"defteam":defteam,"play_type":typ,"bucket":bucket,"description":(desc or "")[:170]})
print(json.dumps({"prototype_special_teams_td":len(items),"by_bucket":dict(collections.Counter(x["bucket"] for x in items)),"by_play_type":dict(collections.Counter(x["play_type"] for x in items)),"events":items,"note":"Compare 26 provisional events to prior 21; investigate classification and kickoff possession semantics. Read-only."},indent=2))
