#!/usr/bin/env python3
"""Review-only priority audit: high-impact Week 8 unmatched and zero PPR records."""
import csv,json,pathlib,collections
base=pathlib.Path("projection-model/validation")
rows=list(csv.DictReader((base/"week8_sunday_ppr_frozen_accuracy_review.csv").open(newline="")))
quality=json.loads((base/"week8_sunday_actuals_quality_gate_review.json").read_text())
annotations=json.loads((base/"week8_sunday_verified_participation_annotations.json").read_text())["annotations"]
snap=list(csv.DictReader(pathlib.Path("model-snapshots/2026-10-31-pregame-ppr-projections.csv").open(newline="")))
known={(a["player"],a["position"],a["team"]):a["status"] for a in annotations}
confirmed_inactive={
 ("Breece Hall","RB","NYJ"),("Brian Robinson Jr.","RB","ATL"),
 ("TreVeyon Henderson","RB","NE"),("RJ Harvey","RB","DEN"),
 ("Tyjae Spears","RB","TEN"),("A.J. Brown","WR","NE"),
 ("Emeka Egbuka","WR","TB"),("DeVonta Smith","WR","PHI"),
 ("Carnell Tate","WR","TEN")
}
snap_idx={(r["player_name"],r["position"],r["team"]):r for r in snap}
priority=[]
for q in quality["unmatched_rows"]:
 key=(q["player"],q["position"],q["team"]);r=snap_idx.get(key)
 if not r:continue
 try:projection=float(r["projected_ppr"])
 except (ValueError,TypeError):continue
 priority.append({"player":q["player"],"position":q["position"],"team":q["team"],"projected_ppr":projection,"actual_ppr":None,"issue":"UNMATCHED","classification":"INACTIVE_CONFIRMED" if key in confirmed_inactive else known.get(key,"UNVERIFIED"),"absolute_error":None})
for r in rows:
 if float(r["actual"])!=0:continue
 key=(r["player"],r["position"],r["team"])
 priority.append({"player":r["player"],"position":r["position"],"team":r["team"],"projected_ppr":float(r["projected"]),"actual_ppr":0,"issue":"ZERO_PPR","classification":known.get(key,"UNVERIFIED_ZERO"),"absolute_error":float(r["absolute_error"])})
priority.sort(key=lambda x:x["projected_ppr"],reverse=True)
out=base/"week8_sunday_high_impact_participation_priority.json"
out.write_text(json.dumps({"status":"REVIEW_ONLY","priority":priority,"notes":["Confirmed inactive list sourced from Week 8 published inactive reports; check identity and team before final model eligibility","Zero-PPR entries remain unverified unless explicitly annotated","Original MAE remains unchanged","No production modifications"]},indent=2)+"\n")
print(json.dumps({"status":"GREEN","total_questionable":len(priority),"confirmed_inactive_in_unmatched":sum(p["classification"]=="INACTIVE_CONFIRMED" for p in priority),"top_20":priority[:20],"saved":str(out),"production_changed":False},indent=2))
