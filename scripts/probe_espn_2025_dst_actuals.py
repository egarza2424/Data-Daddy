#!/usr/bin/env python3
"""Read-only probe for independent ESPN 2025 weekly D/ST actual fantasy scores."""
import json,urllib.request,urllib.error
url="https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/2025/players?view=kona_player_info"
filters={"players":{"filterSlotIds":{"value":[16]},"limit":5,"filterStatsForTopScoringPeriodIds":{"value":[1]},"filterStatsForExternalIds":{"value":[2025]}}}
req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0","Accept":"application/json","X-Fantasy-Filter":json.dumps(filters)})
try:
 with urllib.request.urlopen(req,timeout=25) as response:
  payload=json.load(response)
 print(json.dumps({"status":"response_received","top_level_type":type(payload).__name__,"count":len(payload) if isinstance(payload,list) else None,"sample":[{"id":p.get("id"),"fullName":p.get("fullName"),"defaultPositionId":p.get("defaultPositionId"),"proTeamId":p.get("proTeamId"),"stats":[{"seasonId":s.get("seasonId"),"scoringPeriodId":s.get("scoringPeriodId"),"statSourceId":s.get("statSourceId"),"statSplitTypeId":s.get("statSplitTypeId"),"appliedTotal":s.get("appliedTotal")} for s in p.get("stats",[])[:6]]} for p in (payload if isinstance(payload,list) else payload.get("players",[]))[:5]],"note":"Diagnostic only. Values are ESPN-sourced only if returned by endpoint; verify league scoring context before benchmarking."},indent=2))
except (urllib.error.HTTPError,urllib.error.URLError,TimeoutError,ValueError) as e:
 print(json.dumps({"status":"unavailable","error":str(e),"note":"No ESPN data retrieved; do not claim validation."},indent=2))
