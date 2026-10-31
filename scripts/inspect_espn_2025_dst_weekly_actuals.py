#!/usr/bin/env python3
"""Read-only ESPN 2025 team-defense discovery and weekly actual-score inspection."""
import json,urllib.request,urllib.error,collections
url="https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/2025/players?view=kona_player_info"
filters={"players":{"filterSlotIds":{"value":[16]},"limit":4000}}
req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0","Accept":"application/json","X-Fantasy-Filter":json.dumps(filters)})
try:
 with urllib.request.urlopen(req,timeout=35) as response:players=json.load(response)
 defenses=[p for p in players if p.get("defaultPositionId")==16]
 report=[]
 for p in defenses:
  actual=[s for s in p.get("stats",[]) if s.get("seasonId")==2025 and s.get("statSourceId")==0 and s.get("statSplitTypeId")==1 and 1<=s.get("scoringPeriodId",0)<=18]
  report.append({"name":p.get("fullName"),"id":p.get("id"),"proTeamId":p.get("proTeamId"),"weekly_actual_count":len(actual),"weekly_actual_samples":[{"week":s.get("scoringPeriodId"),"appliedTotal":s.get("appliedTotal"),"rawStatsCount":len(s.get("stats") or {}),"rawStatsSample":dict(list((s.get("stats") or {}).items())[:6])} for s in sorted(actual,key=lambda x:x["scoringPeriodId"])[:3]]})
 print(json.dumps({"returned_records":len(players),"dst_count":len(defenses),"dst_with_actual_weeks":sum(bool(p["weekly_actual_count"]) for p in report),"defenses":report,"caution":"appliedTotal may be null without league scoring settings. Do not treat null as zero or claim score validation."},indent=2))
except (urllib.error.HTTPError,urllib.error.URLError,TimeoutError,ValueError) as e:
 print(json.dumps({"status":"unavailable","error":str(e)}))
