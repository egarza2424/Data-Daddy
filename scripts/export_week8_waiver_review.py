"""Compact review of existing waiver ranks; no ranking changes."""
import json
from pathlib import Path
p=Path("waiver_wire_candidates.json")
d=json.loads(p.read_text(encoding="utf-8"))
c=d.get("candidates",[])
def view(x):
    return {"name":x.get("name"),"team":x.get("team"),"position":x.get("position"),
            "rank":x.get("waiver_rank") or x.get("rank"),
            "evidence_score":x.get("waiver_evidence_score"),
            "rostered_pct":x.get("average_rostered"),
            "recent_ppr":x.get("recent_average_ppr"),
            "opportunity_change":x.get("opportunity_change"),
            "injury_screening":x.get("injury_screening"),
            "injury_review_priority":x.get("injury_review_priority")}
if int(d.get("target_week",0))!=8 or int(d.get("season",0))!=2026:
    raise RuntimeError(f"Expected 2026 Week 8, got {d.get('season')} Week {d.get('target_week')}")
print("DATA DADDY WEEK 8 WAIVER REVIEW — NOT FINAL")
print("Candidate count:",len(c))
print("CURRENT PROVISIONAL TOP 10")
for i,x in enumerate(d.get("provisional_top_10",[]),1):
    print(i,json.dumps(view(x),default=str))
for pos in ("RB","WR","TE","QB"):
    print("TOP",pos,"CANDIDATES")
    for i,x in enumerate([x for x in c if x.get("position")==pos][:10],1):
        print(i,json.dumps(view(x),default=str))
print("FLAGGED PLAYER CHECK")
for name in ("Antonio Williams","Caleb Douglas","Chig Okonkwo","Seth McGowan"):
    matches=[view(x) for x in c if x.get("name")==name]
    print(name,json.dumps(matches,default=str))
print("Review only. No changes to scores, rankings, weights, or site.")
