#!/usr/bin/env python3
"""Read-only: fetch ESPN's own D/ST stat-ID metadata and display candidate labels."""
import json,urllib.request,urllib.error
base="https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/2025"
headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"}
for view in ("proTeamSchedules_wl","mSettings"):
 url=base+"?view="+view
 try:
  with urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=20) as r: obj=json.load(r)
  print(json.dumps({"view":view,"keys":list(obj) if isinstance(obj,dict) else "list","stat_label_candidates":{k:v for k,v in obj.items() if "stat" in k.lower() or "scor" in k.lower()} if isinstance(obj,dict) else {}},default=str)[:5500])
 except Exception as e:print(json.dumps({"view":view,"error":str(e)}))
print("ESPN stat IDs are not mapped by this probe; do not guess scoring from IDs.")
