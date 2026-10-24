"""Read-only Week 7 WR five-game challenger, no production changes."""
import json,csv
from pathlib import Path
from collections import defaultdict
D=json.loads(Path("nfl-stats.json").read_text())
rows=D.get("players",[])
if isinstance(rows,dict):rows=rows.get("weekly_stats",rows.get("weekly",rows.get("stats",[])))
if not rows:
    def search(o):
        if isinstance(o,list):
            if o and isinstance(o[0],dict) and ("player_display_name" in o[0] or "receiving_yards" in o[0]):return o
            for v in o[:4]:
                found=search(v)
                if found:return found
        if isinstance(o,dict):
            for v in o.values():
                if isinstance(v,(dict,list)):
                    found=search(v)
                    if found:return found
        return []
    rows=search(D.get("recent_player_performance",{})) or search(D)
if not isinstance(rows,list):raise RuntimeError("Unsupported weekly row structure")
def norm(s):return " ".join(str(s or "").lower().replace(".","").split())
by=defaultdict(list)
for r in rows:
    if str(r.get("season"))!="2026" or r.get("position")!="WR":continue
    name=norm(r.get("player_display_name") or r.get("player_name") or r.get("name"))
    if name:by[name].append(r)
def val(r,k):return float(r.get(k) or 0)
def ppr(r):return val(r,"receptions")+val(r,"receiving_yards")/10+6*val(r,"receiving_tds")+val(r,"rushing_yards")/10+6*val(r,"rushing_tds")
def metrics(g,n):
    x=sorted(g,key=lambda r:int(r.get("week") or 0),reverse=True)[:n]
    return (sum(ppr(r) for r in x)/len(x),sum(val(r,"targets")+val(r,"carries") for r in x)/len(x))
scores={}
for name,g in by.items():
    if g:scores[name]=(metrics(g,3),metrics(g,5))
if not scores:
    raise RuntimeError("No 2026 WR game rows found; inspect nfl-stats.json source schema")
base_prod=max(v[0][0] for v in scores.values())
new_prod=max(v[1][0] for v in scores.values())
base_opp=max(v[0][1] for v in scores.values())
new_opp=max(v[1][1] for v in scores.values())
with Path("projection-model/current-live-model-snapshot.csv").open(newline="") as f:snapshot=list(csv.DictReader(f))
ranked=[]
for r in snapshot:
    if r["position"]!="WR":continue
    name=norm(r["player_name"])
    if name not in scores:continue
    (oldp,oldo),(newp,newo)=scores[name]
    old_prod=100*oldp/base_prod; new_prod_score=100*newp/new_prod
    old_opp=100*oldo/base_opp;new_opp_score=100*newo/new_opp
    # Approximate fixed-weight challenger, not a full recomputation of all model inputs.
    delta=.2046*(new_prod_score-old_prod)+.1674*(new_opp_score-old_opp)
    ranked.append((float(r["model_score"])+delta,r["player_name"],float(r["model_score"]),delta,len(by[name]),oldp,newp,oldo,newo))
ranked.sort(reverse=True)
for name in ("Justin Jefferson","Courtland Sutton","Nico Collins"):
    found=next(( (i,x) for i,x in enumerate(ranked,1) if x[1]==name),None)
    print(name, "challenger approximate rank among matched WR",found[0] if found else "missing","details",found[1] if found else "")
print("Coverage",len(ranked),"of",sum(r["position"]=="WR" for r in snapshot),"WRs; unmatched WRs omitted from challenger ranking")
print("This is a sensitivity analysis only. Does NOT include changed usage, confidence, editorial adjustments, historical validation or full rank universe. No production edits.")
