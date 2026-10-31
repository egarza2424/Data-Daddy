#!/usr/bin/env python3
"""Read-only ESPN D/ST special-teams TD ID investigation, no production changes."""
import json,urllib.request,collections
url="https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/2025/players?view=kona_player_info"
headers={"User-Agent":"Mozilla/5.0","Accept":"application/json","X-Fantasy-Filter":json.dumps({"players":{"filterSlotIds":{"value":[16]},"limit":4000}})}
with urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=35) as r: players=json.load(r)
out=[]
for p in players:
 if p.get("defaultPositionId")!=16:continue
 for s in p.get("stats",[]):
  if s.get("seasonId")!=2025 or s.get("statSourceId")!=0 or s.get("statSplitTypeId")!=1 or not 1<=s.get("scoringPeriodId",0)<=18:continue
  st=s.get("stats") or {}
  if any(float(st.get(str(k),0))>0 for k in (93,94,101,102,103,104,105,125,196)):
   out.append({"team":p.get("fullName"),"week":s["scoringPeriodId"],"potential_td_fields":{str(k):st.get(str(k),0) for k in (89,90,91,92,93,94,95,96,97,98,101,102,103,104,105,125,128,129,130,131,132,133,134,135,136,188,189,190,191,192,193,194,195,196) if float(st.get(str(k),0))!=0}})
print(json.dumps({"candidate_rows":len(out),"candidate_examples":out[:100],"note":"Inspection only. Field labels and ESPN fantasy points are not independently verified."},indent=2))
