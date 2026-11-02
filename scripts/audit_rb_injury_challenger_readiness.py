#!/usr/bin/env python3
"""Read-only readiness check for a leakage-safe RB injury-opportunity challenger.
Uses only Python standard library; no dependencies required.
"""
import csv
from pathlib import Path
root=Path("projection-model")
val=root/"validation"
need=["season","week","player_id"]
keywords=("injur","inactive","out_","absence","absent","starter","depth","teammate","opportun","snap","touch","carry","target","role")
for season in (2024,2025):
 print("\nSEASON",season)
 for label,path in [("history",root/f"{season}-historical-ppr-dataset.csv"),("J2 predictions",val/f"{season}-rb-model-j2-predictions.csv")]:
  if not path.exists():
   print(label,"MISSING",path)
   continue
  with path.open(newline="",encoding="utf-8-sig") as f:
   reader=csv.DictReader(f)
   columns=reader.fieldnames or []
   sample=next(reader,None)
  print(label,"path",path,"columns",len(columns))
  print(" join keys present:",[c for c in need if c in columns])
  print(" candidate columns:",[c for c in columns if any(k in c.lower() for k in keywords)])
  print(" sample rows:",int(sample is not None))
print("\nNo training, scoring, live files or weights modified.")
