#!/usr/bin/env python3
"""One-time, narrowly scoped Week 8 actual PPR correction confirmed by site owner."""
import json,pathlib
path=pathlib.Path("data/actual-ppr-2026.json")
payload=json.loads(path.read_text())
rows=payload["players"]
matches=[r for r in rows if int(r.get("season",0))==2026 and int(r.get("week",0))==8 and r.get("player_display_name","").casefold().replace(".","").startswith("omar cooper")]
if matches:
 if len(matches)==1 and matches[0].get("team")=="NYJ" and matches[0].get("position")=="WR" and float(matches[0].get("fantasy_points_ppr",-1))==0:
  print("GREEN: Omar Cooper Jr. Week 8 0.00 PPR already recorded; no changes")
 else:raise SystemExit("Existing Omar Cooper Week 8 record requires manual review: "+repr(matches))
else:
 rows.append({"season":2026,"week":8,"player_display_name":"Omar Cooper Jr.","team":"NYJ","position":"WR","fantasy_points_ppr":0.0})
 path.write_text(json.dumps(payload,separators=(",",":"))+"\n")
 print("GREEN: added Omar Cooper Jr. NYJ WR Week 8 actual 0.00 PPR; review and commit data file")
print("No projections, rankings, or model weights changed")
