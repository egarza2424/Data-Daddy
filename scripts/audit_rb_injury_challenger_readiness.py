#!/usr/bin/env python3
"""Read-only readiness check for a leakage-safe RB injury-opportunity challenger."""
from pathlib import Path
import pandas as pd
root=Path("projection-model")
val=root/"validation"
need=["season","week","player_id"]
keywords=("injur","inactive","out_","absence","absent","starter","depth","teammate","opportun","snap","touch","carry","target","role")
for season in (2024,2025):
 print("\nSEASON",season)
 for label,path in [("history",root/f"{season}-historical-ppr-dataset.csv"),("J2 predictions",val/f"{season}-rb-model-j2-predictions.csv")]:
  if not path.exists():
   print(label,"MISSING",path);continue
  d=pd.read_csv(path,nrows=5)
  print(label,"path",path,"columns",len(d.columns))
  print(" join keys present:",[c for c in need if c in d.columns])
  print(" candidate columns:",[c for c in d.columns if any(k in c.lower() for k in keywords)])
  print(" sample rows:",len(d))
print("\nNo training, scoring, live files or weights modified.")
