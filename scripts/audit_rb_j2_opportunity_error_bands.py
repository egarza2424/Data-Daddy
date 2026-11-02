#!/usr/bin/env python3
"""Read-only J2 historical opportunity/error diagnostic; no model challenger or tuning."""
import csv,collections,statistics
from pathlib import Path
root=Path("projection-model"); val=root/"validation"
def read(path):
 with path.open(newline="",encoding="utf-8-sig") as f:return list(csv.DictReader(f))
def num(x):
 try:return float(x)
 except (TypeError,ValueError):return None
def group(x):
 if x<25:return "00-24"
 if x<50:return "25-49"
 if x<75:return "50-74"
 return "75-100"
for season in (2024,2025):
 hist=read(root/f"{season}-historical-ppr-dataset.csv")
 pred=read(val/f"{season}-rb-model-j2-predictions.csv")
 h={}
 for r in hist:
  if r.get("position")!="RB":continue
  key=(r.get("season"),r.get("week"),r.get("player_id"))
  h.setdefault(key,[]).append(r)
 bins=collections.defaultdict(list);matched=0;missing=0
 for p in pred:
  if p.get("model")!="J2_RB_role_stability":continue
  hits=h.get((p.get("season"),p.get("week"),p.get("player_id")),[])
  if len(hits)!=1:missing+=1;continue
  opportunity=num(hits[0].get("opportunity_score"))
  predicted=num(p.get("projected_ppr"));actual=num(p.get("actual_ppr"))
  if opportunity is None or predicted is None or actual is None:missing+=1;continue
  bins[group(opportunity)].append((predicted-actual,abs(predicted-actual)))
  matched+=1
 print("\nSEASON",season,"J2 matched",matched,"missing/ambiguous",missing)
 for band in ("00-24","25-49","50-74","75-100"):
  rows=bins[band]
  if rows:print(" opportunity",band,"n",len(rows),"MAE",round(statistics.mean(x[1] for x in rows),3),"bias",round(statistics.mean(x[0] for x in rows),3))
print("\nDiagnostic only: association does not establish causation or pregame availability of features.")
print("No challenger trained, no weights or production changed.")
