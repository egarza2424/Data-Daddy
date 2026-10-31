#!/usr/bin/env python3
"""Read-only weekly top-12 ranking validation for historical D/ST challengers."""
import csv,json,pathlib,collections
p=pathlib.Path("projection-model/validation/dst_2024_2025_incremental_opponent_risk_challenger.csv")
if not p.exists():raise SystemExit("Missing historical challenger CSV. Run python scripts/backtest_dst_incremental_opponent_risk.py first.")
with p.open(newline="") as f:rows=list(csv.DictReader(f))
models=["v1","v1_plus_sacks","v1_plus_ints","v1_plus_both"]
groups=collections.defaultdict(list)
for r in rows:groups[(int(r["season"]),int(r["week"]))].append(r)
def average(xs):return round(sum(xs)/len(xs),4) if xs else None
results={}
details=[]
for m in models:
 hits=[];precisions=[];regrets=[];actuals=[];ranks=[];top12_mae=[]
 for (season,week),weekrows in sorted(groups.items()):
  if len(weekrows)<12:raise SystemExit(f"Too few defenses for {season} W{week}")
  # Stable tie breaking ensures reproducible comparisons.
  predicted=sorted(weekrows,key=lambda r:(-float(r[m]),r["defense"]))[:12]
  actual=sorted(weekrows,key=lambda r:(-float(r["actual"]),r["defense"]))[:12]
  actual_ids={r["defense"] for r in actual}
  overlap=sum(r["defense"] in actual_ids for r in predicted)
  pred_points=sum(float(r["actual"]) for r in predicted)
  ideal_points=sum(float(r["actual"]) for r in actual)
  hits.append(overlap);precisions.append(overlap/12)
  regrets.append(ideal_points-pred_points)
  actuals.append(pred_points/12)
  top12_mae.extend(abs(float(r[m])-float(r["actual"])) for r in predicted)
  actual_rank={r["defense"]:i+1 for i,r in enumerate(sorted(weekrows,key=lambda r:(-float(r["actual"]),r["defense"])))}
  ranks.extend(actual_rank[r["defense"]] for r in predicted)
  details.append({"model":m,"season":season,"week":week,"top12_overlap":overlap,
   "precision_at_12":round(overlap/12,4),"actual_points_selected":round(pred_points,3),
   "actual_points_ideal":round(ideal_points,3),"regret":round(ideal_points-pred_points,3)})
 results[m]={"weeks":len(hits),"mean_top12_hits":average(hits),
  "precision_at_12":average(precisions),
  "mean_actual_points_per_selected_defense":average(actuals),
  "mean_weekly_top12_points_regret":average(regrets),
  "mean_actual_rank_of_selected":average(ranks),
  "selected_top12_prediction_mae":average(top12_mae)}
dest=pathlib.Path("projection-model/validation/dst_top12_ranking_comparison_review.csv")
dest.parent.mkdir(parents=True,exist_ok=True)
with dest.open("w",newline="") as f:
 w=csv.DictWriter(f,fieldnames=list(details[0]));w.writeheader();w.writerows(details)
print(json.dumps({"status":"REVIEW_ONLY","historical_weeks":len(groups),
 "defense_games":len(rows),"results":results,"saved":str(dest),
 "notes":["Top-12 measured against same-week actual best 12 among eligible evaluated defenses",
 "Points regret is oracle gap, not an achievable real-world forecast",
 "Predicted top-12 selection uses each model's own scores",
 "Historical candidate coefficients remain exploratory; no live model changes"],
 "production_changed":False},indent=2))
