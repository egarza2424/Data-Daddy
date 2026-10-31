#!/usr/bin/env python3
"""Read-only walk-forward D/ST feature challenger, 2025 reconstructed ESPN-stat targets.
Predictions use only prior weeks. Fixed shrinkage coefficients; no training on test weeks.
"""
import csv,collections,json,math,pathlib
src=pathlib.Path("projection-model/validation/dst_2025_espn_stat_based_scores.csv")
if not src.exists():raise SystemExit("Missing scores CSV. Run python scripts/export_dst_2025_espn_stat_based_csv.py")
with src.open(newline="") as f:rows=list(csv.DictReader(f))
by_week=collections.defaultdict(list)
for r in rows:
 r["week"]=int(r["week"])
 for k in ("reconstructed_dst_points","espn_sacks","espn_interceptions","espn_fumble_recoveries","espn_points_allowed"):r[k]=float(r[k])
 by_week[r["week"]].append(r)
def avg(xs):return sum(xs)/len(xs) if xs else 0.
hist=collections.defaultdict(list);offhist=collections.defaultdict(list);out=[]
for week in sorted(by_week):
 prior=[r for rs in hist.values() for r in rs]
 if prior:
  baseline=avg([r["reconstructed_dst_points"] for r in prior])
  league_sacks=avg([r["espn_sacks"] for r in prior])
  league_takeaways=avg([r["espn_interceptions"]+r["espn_fumble_recoveries"] for r in prior])
  league_pa=avg([r["espn_points_allowed"] for r in prior])
 for r in by_week[week]:
  away,home=r["game_id"].split("_")[-2:]
  defense=r["defense"];opponent=home if defense==away else away
  dh=hist[defense];oh=offhist[opponent]
  if week<5 or len(dh)<3 or len(oh)<3:continue
  # Shrunk defensive rates; offense vulnerability is prior fantasy D/ST points allowed.
  ds=(sum(x["espn_sacks"] for x in dh)+5*league_sacks)/(len(dh)+5)
  dt=(sum(x["espn_interceptions"]+x["espn_fumble_recoveries"] for x in dh)+8*league_takeaways)/(len(dh)+8)
  dpa=(sum(x["espn_points_allowed"] for x in dh)+8*league_pa)/(len(dh)+8)
  opp=(sum(x["reconstructed_dst_points"] for x in oh)+8*baseline)/(len(oh)+8)
  variants={
   "global":baseline,
   "sacks":baseline+0.8*(ds-league_sacks),
   "sacks_takeaways":baseline+0.8*(ds-league_sacks)+0.8*(dt-league_takeaways),
   "opponent":baseline+0.5*(opp-baseline),
   "all":baseline+0.8*(ds-league_sacks)+0.8*(dt-league_takeaways)+0.5*(opp-baseline)-0.05*(dpa-league_pa)
  }
  out.append({"week":week,"defense":defense,"opponent":opponent,"actual":r["reconstructed_dst_points"],**variants})
 for r in by_week[week]:
  away,home=r["game_id"].split("_")[-2:]
  opponent=home if r["defense"]==away else away
  hist[r["defense"]].append(r);offhist[opponent].append(r)
metrics={}
for key in ("global","sacks","sacks_takeaways","opponent","all"):
 errors=[r[key]-r["actual"] for r in out]
 metrics[key]={"mae":round(avg([abs(x) for x in errors]),4),"rmse":round(math.sqrt(avg([x*x for x in errors])),4)}
dest=pathlib.Path("projection-model/validation/dst_2025_feature_challenger_predictions.csv")
with dest.open("w",newline="") as f:
 w=csv.DictWriter(f,fieldnames=["week","defense","opponent","actual","global","sacks","sacks_takeaways","opponent","all"])
 w.writeheader();w.writerows(out)
print(json.dumps({"evaluated":len(out),"metrics":metrics,"best_mae":min(metrics,key=lambda x:metrics[x]["mae"]),"saved":str(dest),"note":"Fixed illustrative weights, not tuned; 2025 only, reconstructed targets; no live changes."},indent=2))
