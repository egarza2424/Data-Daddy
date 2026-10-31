#!/usr/bin/env python3
"""Read-only 2025 D/ST walk-forward baseline; no live model changes.

Uses only completed prior-week games to predict the next defense game.
Tests historical mean vs recency and opponent offense points allowed to defenses.
"""
import csv,collections,statistics,math,json,pathlib
p=pathlib.Path("projection-model/validation/dst_2025_espn_stat_based_scores.csv")
if not p.exists():raise SystemExit("Missing historical CSV. Run python scripts/export_dst_2025_espn_stat_based_csv.py")
with p.open(newline="") as f:rows=list(csv.DictReader(f))
for r in rows:
 r["week"]=int(r["week"])
 for k in ("reconstructed_dst_points","espn_sacks","espn_interceptions","espn_fumble_recoveries","espn_points_allowed"):r[k]=float(r[k])
by_week=collections.defaultdict(list)
for r in rows:by_week[r["week"]].append(r)
hist=collections.defaultdict(list);offense=collections.defaultdict(list);predictions=[]
def avg(seq):return sum(seq)/len(seq) if seq else 0
for week in sorted(by_week):
 # All predictions generated before adding any game from this week to histories.
 for r in by_week[week]:
  parts=r["game_id"].split("_")
  if len(parts)<4:raise SystemExit("Unexpected game_id "+r["game_id"])
  away,home=parts[-2:]
  opponent=home if r["defense"]==away else away
  if r["defense"] not in (home,away):raise SystemExit("Defense mismatch "+r["game_id"])
  dh=hist[r["defense"]];oh=offense[opponent]
  if week<5 or len(dh)<3 or len(oh)<3:continue
  global_prior=[x["reconstructed_dst_points"] for t in hist.values() for x in t]
  global_mean=avg(global_prior)
  season=avg([x["reconstructed_dst_points"] for x in dh])
  recent=avg([x["reconstructed_dst_points"] for x in dh[-4:]])
  # Opponent vulnerability = points previously scored by D/STs facing that offense.
  opponent_vulnerability=avg(oh[-4:])
  predictions.append({"week":week,"defense":r["defense"],"opponent":opponent,"actual":r["reconstructed_dst_points"],"global":global_mean,"season":season,"recent":recent,"blend":.5*season+.5*recent,"opponent":opponent,"opponent_blend":.5*recent+.5*opponent_vulnerability})
 for r in by_week[week]:
  parts=r["game_id"].split("_");away,home=parts[-2:]
  opponent=home if r["defense"]==away else away
  hist[r["defense"]].append(r)
  offense[opponent].append(r["reconstructed_dst_points"])
metrics={}
for key in ("global","season","recent","blend","opponent_blend"):
 errors=[abs(x[key]-x["actual"]) for x in predictions]
 metrics[key]={"mae":round(avg(errors),4),"rmse":round(math.sqrt(avg([(x[key]-x["actual"])**2 for x in predictions])),4)}
out=pathlib.Path("projection-model/validation/dst_2025_walk_forward_baseline_predictions.csv")
out.parent.mkdir(parents=True,exist_ok=True)
with out.open("w",newline="") as f:
 w=csv.DictWriter(f,fieldnames=["week","defense","opponent","actual","global","season","recent","blend","opponent_blend"]);w.writeheader();w.writerows(predictions)
print(json.dumps({"status":"read_only_research","rows":len(rows),"evaluated":len(predictions),"weeks":"5-18","metrics":metrics,"best_mae":min(metrics,key=lambda k:metrics[k]["mae"]),"predictions_csv":str(out),"limitations":["2025 only; no prior-season history; weeks 1-4 excluded","Targets reconstructed from ESPN raw stats, not official ESPN fantasy point totals","Simple baseline, no fitted weights or 2026 production deployment"],"production_changed":False},indent=2))
