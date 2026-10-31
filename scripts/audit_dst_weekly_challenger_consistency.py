#!/usr/bin/env python3
"""Compare weekly top-12 D/ST selection points versus V1, review-only."""
import collections,csv,json,pathlib,statistics
src=pathlib.Path("projection-model/validation/dst_top12_ranking_comparison_review.csv")
if not src.exists():raise SystemExit("Missing top-12 review CSV; run scripts/audit_dst_top12_ranking_accuracy.py first.")
with src.open(newline="") as f:rows=list(csv.DictReader(f))
byweek=collections.defaultdict(dict)
for r in rows:
 key=(int(r["season"]),int(r["week"]))
 if r["model"] in byweek[key]:raise SystemExit(f"Duplicate model row: {key} {r['model']}")
 byweek[key][r["model"]]=r
models=("v1_plus_sacks","v1_plus_ints","v1_plus_both")
details=[];summary={}
for model in models:
 deltas=[];hits=[];wins=ties=losses=0
 for key,modelrows in sorted(byweek.items()):
  if "v1" not in modelrows or model not in modelrows:raise SystemExit(f"Missing comparison for {key}: {model}")
  baseline=modelrows["v1"];challenger=modelrows[model]
  # CSV values were rounded to 3 decimals; equality within .001 is a tie.
  delta=float(challenger["actual_points_selected"])-float(baseline["actual_points_selected"])
  hit_delta=int(challenger["top12_overlap"])-int(baseline["top12_overlap"])
  if delta>0.001:wins+=1
  elif delta< -0.001:losses+=1
  else:ties+=1
  deltas.append(delta);hits.append(hit_delta)
  details.append({"season":key[0],"week":key[1],"challenger":model,
   "v1_selected_points":baseline["actual_points_selected"],
   "challenger_selected_points":challenger["actual_points_selected"],
   "delta_selected_points":round(delta,3),
   "v1_top12_hits":baseline["top12_overlap"],
   "challenger_top12_hits":challenger["top12_overlap"],
   "delta_top12_hits":hit_delta})
 summary[model]={"weeks":len(deltas),"wins":wins,"ties":ties,"losses":losses,
  "mean_weekly_points_delta":round(statistics.mean(deltas),4),
  "median_weekly_points_delta":round(statistics.median(deltas),4),
  "total_extra_top12_hits":sum(hits),
  "weeks_with_more_top12_hits":sum(x>0 for x in hits),
  "weeks_with_fewer_top12_hits":sum(x<0 for x in hits),
  "best_week_delta":round(max(deltas),3),"worst_week_delta":round(min(deltas),3),
  "by_season":{str(y):{"wins":sum(x["season"]==y and x["delta_selected_points"]>0.001 for x in details if x["challenger"]==model),
    "ties":sum(x["season"]==y and abs(x["delta_selected_points"])<=0.001 for x in details if x["challenger"]==model),
    "losses":sum(x["season"]==y and x["delta_selected_points"]< -0.001 for x in details if x["challenger"]==model)}
    for y in (2024,2025)}}
dest=pathlib.Path("projection-model/validation/dst_weekly_challenger_consistency_review.csv")
with dest.open("w",newline="") as f:
 w=csv.DictWriter(f,fieldnames=list(details[0]));w.writeheader();w.writerows(details)
print(json.dumps({"status":"REVIEW_ONLY","results":summary,"saved":str(dest),
 "notes":["Compares realized total points of 12 selected defenses each week",
 "Ties mean points within 0.001 after rounding","No tuning, weights, rankings, or production changes"],
 "production_changed":False},indent=2))
