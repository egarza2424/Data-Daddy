"""Diagnose missing players across snapshot and projections without changing live output."""
import csv,re
from pathlib import Path
def load(p):
 with open(p,newline="",encoding="utf-8") as f:return list(csv.DictReader(f))
def norm(s):
 s=str(s).casefold().strip()
 s=re.sub(r"\s+(jr\.?|sr\.?|ii|iii|iv)$","",s)
 return re.sub(r"[^a-z0-9]","",s)
targets=["Omar Cooper","Antonio Williams","Jordan Mason"]
paths=["projection-model/current-live-model-snapshot.csv","projection-model/2026-week7-ppr-projections.csv","projection-model/2026-week7-market-consensus.csv"]
for path in paths:
 p=Path(path)
 if not p.exists():print(path,"MISSING FILE");continue
 rows=load(p)
 print("\n",path,"total",len(rows))
 for target in targets:
  matches=[r for r in rows if norm(r.get("player_name",""))==norm(target)]
  print(target,"matches",len(matches),[(r.get("player_name"),r.get("team"),r.get("position"),r.get("player_id"),r.get("snapshot_week"),r.get("projected_ppr")) for r in matches[:5]])
print("\nNo production edits.")
