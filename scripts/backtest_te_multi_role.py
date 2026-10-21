"""Week 6 holdout: compare frozen TE AI ranks with pregame multi-TE role adjustment.

Only weeks <=5 may generate the new signal. Week 6 actual PPR is evaluation only.
"""
import csv, json
from collections import defaultdict
from pathlib import Path

STATS = Path("nfl-stats.json")
VALID = Path("model-validation/2026-week6-validation.csv")
PROJ = Path("projection-model/2026-week6-ppr-projections.csv")
OUT = Path("model-validation/2026-week6-te-multi-role-holdout.csv")
rows = json.loads(STATS.read_text(encoding="utf-8"))
if isinstance(rows, dict):
    rows = next((rows[k] for k in ("players", "stats", "data", "rows") if isinstance(rows.get(k), list)), [])
if not isinstance(rows, list): raise SystemExit("No player-week rows in nfl-stats.json")
games = defaultdict(list)
for r in rows:
    if str(r.get("position", "")).upper() != "TE" or int(r.get("season") or 0) != 2026: continue
    week = int(r.get("week") or 0)
    if not 1 <= week <= 5: continue
    name = str(r.get("player_display_name") or r.get("player_name") or r.get("name") or "").strip().lower()
    team = str(r.get("team") or "")
    if name and team: games[(team,week)].append((name,float(r.get("targets") or 0)))
role = defaultdict(set)
for (team,week), tes in games.items():
    for name, targets in tes:
        if targets >= 3 and any(other != name and t >= 2 for other,t in tes):
            role[(team,name)].add(week)
with PROJ.open(newline="",encoding="utf-8") as f:
    projections = {r["player_id"]:r for r in csv.DictReader(f) if r["position"]=="TE"}
with VALID.open(newline="",encoding="utf-8") as f:
    validation = {r["player_id"]:r for r in csv.DictReader(f) if r["position"]=="TE" and r.get("actual_ppr","")!=""}
cohort=[]
for pid,v in validation.items():
    p=projections.get(pid)
    if not p: continue
    key=(p["team"],p["player_name"].strip().lower())
    bonus=6 if len(role.get(key,set())) >= 2 else 0
    baseline=float(v["model_score"])
    # Live AI weights: Usage 0.1395. Only additive delta is tested.
    cohort.append(dict(player_id=pid,player=p["player_name"],team=p["team"],actual_ppr=float(v["actual_ppr"]),
                       baseline_score=baseline,adjusted_score=baseline+bonus*.1395,
                       pregame_shared_role_weeks=len(role.get(key,set())),bonus=bonus))
if len(cohort)<12: raise SystemExit(f"Only {len(cohort)} matched TE rows; cannot assess")
actual_order=sorted(cohort,key=lambda x:(-x["actual_ppr"],x["player_id"]))
actual_rank={r["player_id"]:i+1 for i,r in enumerate(actual_order)}
def measure(field):
    ranked=sorted(cohort,key=lambda x:(-x[field],x["player_id"]))
    predicted_top={r["player_id"] for r in ranked[:24]}
    actual_top=set(actual_rank.keys()) & {r["player_id"] for r in actual_order[:24]}
    hits=len(predicted_top & actual_top)
    mae=sum(abs(i-actual_rank[r["player_id"]]) for i,r in enumerate(ranked,1))/len(ranked)
    return hits,mae,{r["player_id"]:i for i,r in enumerate(ranked,1)}
before=measure("baseline_score");after=measure("adjusted_score")
for r in cohort:
    r["baseline_rank"]=before[2][r["player_id"]]
    r["adjusted_rank"]=after[2][r["player_id"]]
    r["actual_rank"]=actual_rank[r["player_id"]]
OUT.parent.mkdir(parents=True,exist_ok=True)
with OUT.open("w",newline="",encoding="utf-8") as f:
    writer=csv.DictWriter(f,fieldnames=list(cohort[0]));writer.writeheader();writer.writerows(sorted(cohort,key=lambda r:r["baseline_rank"]))
print(f"Matched TEs: {len(cohort)}; eligible pregame role boosts: {sum(r['bonus']>0 for r in cohort)}")
print(f"Baseline top-24 hits {before[0]}/24; rank MAE {before[1]:.3f}")
print(f"Adjusted top-24 hits {after[0]}/24; rank MAE {after[1]:.3f}")
print(f"Delta hits {after[0]-before[0]:+d}; delta MAE {after[1]-before[1]:+.3f}")
print(f"Saved {OUT}")
print("Caution: This isolates an AI score adjustment; it does not retrain the PPR projection model.")
