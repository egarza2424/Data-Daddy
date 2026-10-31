#!/usr/bin/env python3
"""Read-only scenario: compare raw 2025 offensive yards with text-derived sack corrections."""
import duckdb,re,collections,json,sys
src=sys.argv[1] if len(sys.argv)>1 else "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_2025.parquet"
db=duckdb.connect()
rows=db.execute("""SELECT game_id,week,home_team,away_team,posteam,defteam,play_type,yards_gained,sack,"desc"
FROM read_parquet(?) WHERE season=2025 AND week BETWEEN 1 AND 18
AND game_id IS NOT NULL AND play_id IS NOT NULL AND COALESCE(play_type,'') <> 'GAME'
ORDER BY game_id,play_id""",[src]).fetchall()
data=collections.defaultdict(lambda:collections.Counter());changes=[]
for game,week,home,away,off,defteam,typ,yards,sack,desc in rows:
 for team in (home,away):data[(week,game,team)]
 if not off or not defteam or typ not in ("run","pass"):continue
 s=data[(week,game,defteam)]
 s["raw_yards_allowed"]+=yards or 0
 if sack==1 and yards==0:
  m=re.search(r'\bsacked\b[^.]{0,150}?\bfor\s+(-?\d+)\s+yards?',desc or "",re.I)
  if m and int(m.group(1))<0:
   correction=int(m.group(1))
   s["candidate_sack_correction"]+=correction
   s["flagged_sack_fumbles"]+=1
   changes.append({"week":week,"game_id":game,"offense":off,"defense":defteam,"sack_yards_in_description":correction})
output=[{"week":week,"game_id":game,"defense":team,"raw_yards_allowed":s["raw_yards_allowed"],"candidate_correction":s["candidate_sack_correction"],"adjusted_candidate_yards_allowed":s["raw_yards_allowed"]+s["candidate_sack_correction"]} for (week,game,team),s in sorted(data.items()) if s["flagged_sack_fumbles"]]
print(json.dumps({"team_games":len(data),"flagged_plays":len(changes),"affected_team_games":len(output),"total_raw_yards_allowed":sum(s["raw_yards_allowed"] for s in data.values()),"candidate_total_yards_allowed":sum(s["raw_yards_allowed"]+s["candidate_sack_correction"] for s in data.values()),"affected_games":output,"flagged_plays_detail":changes,"caution":"Candidate scenario only: textual sack yardage may not equal official net team offense on fumble plays. No scoring or production files changed."},indent=2))
