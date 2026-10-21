"""Week 6 read-only TE target-trend sensitivity test.

Only weeks 1-5 generate trend. Week 6 actual PPR is held out.
Frozen model_score is a proxy, not a complete reconstruction of live AI scores.
"""
import csv
import json
from collections import defaultdict
from pathlib import Path

STATS=Path("nfl-stats.json")
VALID=Path("model-validation/2026-week6-validation.csv")
OUT=Path("model-validation/2026-week6-te-target-trend-audit.csv")
WEIGHT=0.1395  # Balanced profile usage weight
raw=json.loads(STATS.read_text(encoding="utf-8"))
rows=raw if isinstance(raw,list) else next((raw[k] for k in ("players","stats","data","rows") if isinstance(raw.get(k),list)),[])
if not rows: raise SystemExit("No weekly player stats found")
teams=defaultdict(float)
player_games=defaultdict(list)
for row in rows:
    try: season=int(row.get("season") or 0);week=int(row.get("week") or 0)
    except (TypeError,ValueError): continue
    if season!=2026 or not 1<=week<=5: continue
    team=str(row.get("team") or row.get("recent_team") or "").strip().upper()
    if not team: continue
    targets=float(row.get("targets") or 0)
    teams[(team,week)]+=targets
    if str(row.get("position") or "").upper()=="TE":
        name=str(row.get("player_display_name") or row.get("player_name") or row.get("name") or "").strip().casefold()
        if name: player_games[(team,name)].append((week,targets))
with VALID.open(newline="",encoding="utf-8") as f: valid=list(csv.DictReader(f))
cohort=[]
for row in valid:
    if row.get("position")!="TE" or not row.get("actual_ppr") or not row.get("model_score"): continue
    name=str(row.get("player_name") or "").strip().casefold()
    matches=[(key,games) for key,games in player_games.items() if key[1]==name]
    if len(matches)!=1: continue
    (team,_),games=matches[0]
    recent=sorted(games,reverse=True)[:3]
    shares=[targets/teams[(team,week)] for week,targets in recent if teams[(team,week)]>0]
    if len(shares)<3: continue
    # Most recent game's target share compared with prior two-game average.
    # Clamp effect to +/- 10 usage points; this is an isolated sensitivity test.
    delta=max(-10,min(10,round((shares[0]-(shares[1]+shares[2])/2)*100)))
    baseline=float(row["model_score"])
    cohort.append(dict(player_id=row["player_id"],player=row["player_name"],team=team,
        actual_ppr=float(row["actual_ppr"]),baseline_score=baseline,
        recent_target_share=round(shares[0],4),prior_two_target_share=round((shares[1]+shares[2])/2,4),
        usage_delta=delta,adjusted_proxy_score=baseline+delta*WEIGHT))
if len(cohort)<12: raise SystemExit(f"Only {len(cohort)} matched TEs with 3 pregame games; insufficient")
actual=sorted(cohort,key=lambda x:(-x["actual_ppr"],x["player_id"]))
actual_rank={r["player_id"]:i+1 for i,r in enumerate(actual)}
actual_top={r["player_id"] for r in actual[:24]}
def measure(field):
    order=sorted(cohort,key=lambda x:(-x[field],x["player_id"]))
    ranks={r["player_id"]:i+1 for i,r in enumerate(order)}
    hits=len({r["player_id"] for r in order[:24]} & actual_top)
    mae=sum(abs(ranks[r["player_id"]]-actual_rank[r["player_id"]]) for r in cohort)/len(cohort)
    return hits,mae,ranks
before=measure("baseline_score");after=measure("adjusted_proxy_score")
for row in cohort:
    row["baseline_rank"]=before[2][row["player_id"]]
    row["adjusted_rank"]=after[2][row["player_id"]]
    row["actual_rank"]=actual_rank[row["player_id"]]
OUT.parent.mkdir(parents=True,exist_ok=True)
with OUT.open("w",newline="",encoding="utf-8") as f:
    writer=csv.DictWriter(f,fieldnames=list(cohort[0]))
    writer.writeheader();writer.writerows(sorted(cohort,key=lambda r:r["baseline_rank"]))
print(f"Matched TEs: {len(cohort)}")
print(f"Baseline top-24 hits: {before[0]}; rank MAE: {before[1]:.3f}")
print(f"Trend-adjusted top-24 hits: {after[0]}; rank MAE: {after[1]:.3f}")
print(f"Delta hits: {after[0]-before[0]:+d}; delta MAE: {after[1]-before[1]:+.3f}")
print(f"Saved {OUT}")
print("Proxy sensitivity only. No live AI Score or PPR changes.")
