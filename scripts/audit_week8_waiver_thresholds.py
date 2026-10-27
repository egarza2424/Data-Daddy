"""Read-only Week 8 waiver threshold audit; no scores/ranks modified.

16 QB, 10 RB/WR, 8 TE. Recent PPR is supporting evidence,
not a verified next-week projection or future role guarantee.
"""
import json
from pathlib import Path

d=json.loads(Path("waiver_wire_candidates.json").read_text())
if (int(d.get("season",0)),int(d.get("target_week",0)))!=(2026,8):
    raise SystemExit("Expected 2026 Week 8 candidate file")
thresholds={"QB":16,"RB":10,"WR":10,"TE":8}
rows=d.get("candidates",[])
print("WEEK 8 FANTASY-VALUE THRESHOLD AUDIT — REVIEW ONLY")
print("Minimum weekly fantasy points: QB 16, RB 10, WR 10, TE 8")
print("Recent PPR is NOT a Week 8 projection.")
for pos,threshold in thresholds.items():
    eligible=[x for x in rows if x.get("position")==pos and x.get("ownership_eligible") is True]
    passing=[]
    for x in eligible:
        try: avg=float(x.get("recent_average_ppr"))
        except (TypeError,ValueError):continue
        if avg>=threshold:passing.append(x)
    print(f"\n{pos}: {len(passing)} of {len(eligible)} clear recent PPR threshold {threshold}")
    for x in passing[:20]:
        print(json.dumps({"name":x.get("name"),"team":x.get("team"),
          "preliminary_rank":x.get("preliminary_waiver_rank"),
          "score":x.get("waiver_evidence_score"),"recent_ppr":x.get("recent_average_ppr"),
          "opportunity_change":x.get("opportunity_change"),
          "injury_screening":x.get("injury_screening"),
          "ownership":x.get("average_rostered")}))
print("\nFUTURE-VALUE WATCHLIST: below recent PPR threshold; no automatic promotion")
for x in rows:
    if x.get("name") in ("Antonio Williams","Caleb Douglas","Chig Okonkwo","Seth McGowan","Colby Parkinson","Davis Allen"):
        print(json.dumps({"name":x.get("name"),"position":x.get("position"),
          "recent_ppr":x.get("recent_average_ppr"),
          "threshold":thresholds.get(x.get("position")),
          "opportunity_change":x.get("opportunity_change"),
          "score":x.get("waiver_evidence_score"),
          "preliminary_rank":x.get("preliminary_waiver_rank")}))
print("No production changes.")
