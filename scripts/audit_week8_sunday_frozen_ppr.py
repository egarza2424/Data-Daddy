#!/usr/bin/env python3
"""Review-only full Week 8 accuracy audit from frozen pregame PPR snapshot.
All final games included. Unmatched players are reported, never scored as zero.
No ranking/model/projection modifications.
"""
import collections,csv,json,pathlib,statistics
root=pathlib.Path(".")
snapshot=root/"model-snapshots/2026-10-31-pregame-ppr-projections.csv"
actual_file=root/"data/actual-ppr-2026.json"
if not snapshot.exists() or not actual_file.exists():raise SystemExit("Missing frozen snapshot or actual feed")
rows=list(csv.DictReader(snapshot.open(newline="")))
actual=json.loads(actual_file.read_text())["players"]
def norm(v):
 import re
 s=re.sub(r"[.'’\-]","",str(v or "").lower()).strip()
 return re.sub(r"\s+(jr|sr|ii|iii|iv|v)$","",re.sub(r"\s+"," ",s))
def team(v):return {"LA":"LAR","JAC":"JAX","WSH":"WAS"}.get(str(v).upper(),str(v).upper())
idx=collections.defaultdict(list)
for a in actual:
 if int(a.get("season",0))==2026 and int(a.get("week",0))==8:
  idx[(norm(a.get("player_display_name")),str(a.get("position","")).upper(),team(a.get("team")))].append(a)
result=[];unmatched=[]
for row in rows:
 if row["position"] not in ("QB","RB","WR","TE"):continue
 key=(norm(row["player_name"]),row["position"],team(row["team"]))
 hits=idx.get(key,[])
 if len(hits)!=1:
  unmatched.append({"player":row["player_name"],"position":row["position"],"team":row["team"],"matches":len(hits),"projected_ppr":row.get("projected_ppr"),"roster_status":row.get("roster_status"),"injury_status":row.get("injury_status"),"reason":"missing_actual_or_identity_mismatch" if not hits else "ambiguous_actual","audit_disposition":"excluded_missing_verified_actual","injury_verification":"pending_independent_participation_check"})
  continue
 try:pred=float(row["projected_ppr"]);actual_ppr=float(hits[0]["fantasy_points_ppr"])
 except (TypeError,ValueError,KeyError):continue
 result.append({"player":row["player_name"],"position":row["position"],"team":row["team"],"projected":round(pred,2),"actual":round(actual_ppr,2),"error":round(pred-actual_ppr,2),"absolute_error":round(abs(pred-actual_ppr),2),"projected_position_rank":row["projected_position_rank"],"model":row["projection_model"]})
if len(result)<100:raise SystemExit(f"Insufficient matched rows ({len(result)}); audit not saved")
summary={}
for pos in ("QB","RB","WR","TE"):
 rs=[r for r in result if r["position"]==pos]
 if not rs:continue
 summary[pos]={"matched":len(rs),"mae":round(statistics.mean(r["absolute_error"] for r in rs),3),"bias_projected_minus_actual":round(statistics.mean(r["error"] for r in rs),3),"largest_overprojections":sorted(rs,key=lambda r:r["error"],reverse=True)[:5],"largest_underprojections":sorted(rs,key=lambda r:r["error"])[:5]}
out=root/"projection-model/validation";out.mkdir(parents=True,exist_ok=True)
csv_path=out/"week8_full_ppr_frozen_accuracy_review.csv"
with csv_path.open("w",newline="") as f:
 w=csv.DictWriter(f,fieldnames=list(result[0]));w.writeheader();w.writerows(result)
payload={"season":2026,"week":8,"status":"REVIEW_ONLY","matched":len(result),"unmatched":unmatched,"by_position":summary,"all_mae":round(statistics.mean(r["absolute_error"] for r in result),3),"notes":["Saturday 2026-10-31 frozen pregame snapshot","All final Week 8 games included","Unmatched players excluded from MAE; injury and inactive statuses require independent confirmation","No model weights, live projections, rankings or site files changed"],"csv":str(csv_path)}
json_path=out/"week8_full_ppr_frozen_accuracy_review.json";json_path.write_text(json.dumps(payload,indent=2)+"\n")
print(json.dumps({"status":"GREEN","unmatched_excluded_from_mae":True,"injury_verification":"PENDING","matched":len(result),"unmatched":len(unmatched),"unmatched_examples":unmatched[:15],"overall_mae":payload["all_mae"],"by_position":{k:{"matched":v["matched"],"mae":v["mae"],"bias":v["bias_projected_minus_actual"],"largest_overprojections":v["largest_overprojections"][:3],"largest_underprojections":v["largest_underprojections"][:3]} for k,v in summary.items()},"json":str(json_path),"csv":str(csv_path),"production_changed":False},indent=2))
