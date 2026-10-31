#!/usr/bin/env python3
"""Read-only ESPN D/ST weekly raw-stat field discovery; no scoring assumptions."""
import json,urllib.request,collections
url="https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/2025/players?view=kona_player_info"
headers={"User-Agent":"Mozilla/5.0","Accept":"application/json","X-Fantasy-Filter":json.dumps({"players":{"filterSlotIds":{"value":[16]},"limit":4000}})}
with urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=35) as r: players=json.load(r)
dst=[p for p in players if p.get("defaultPositionId")==16]
rows=[]
for p in dst:
 for s in p.get("stats",[]):
  if s.get("seasonId")==2025 and s.get("statSourceId")==0 and s.get("statSplitTypeId")==1 and 1<=s.get("scoringPeriodId",0)<=18:
   rows.append((p.get("fullName"),s["scoringPeriodId"],s.get("stats") or {}))
fields=collections.Counter(k for _,_,stats in rows for k in stats)
print(json.dumps({"defenses":len(dst),"weekly_rows":len(rows),"field_coverage":dict(sorted(fields.items(),key=lambda kv:int(kv[0]))),"examples":[{"defense":name,"week":week,"all_stats":dict(sorted(stats.items(),key=lambda kv:int(kv[0])))} for name,week,stats in rows if week==1 and name in ("Colts D/ST","Rams D/ST","Chiefs D/ST")],"note":"Raw ESPN field IDs only. No inferred definitions, no scoring changes."},indent=2))
