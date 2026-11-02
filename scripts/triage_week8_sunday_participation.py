#!/usr/bin/env python3
"""Review-only Week 8 actuals participation evidence; never infer DNP from zero PPR."""
import collections,csv,json,pathlib
base=pathlib.Path("projection-model/validation")
audit=list(csv.DictReader((base/"week8_sunday_ppr_frozen_accuracy_review.csv").open(newline="")))
quality=json.loads((base/"week8_sunday_actuals_quality_gate_review.json").read_text())
feed=json.loads(pathlib.Path("data/actual-ppr-2026.json").read_text())["players"]
def norm(v):
 import re
 return re.sub(r"\\s+(jr|sr|ii|iii|iv|v)$","",re.sub(r"\\s+"," ",re.sub(r"[.'’\\-]","",str(v or "").lower())).strip())
def team(v):return {"LA":"LAR","JAC":"JAX","WSH":"WAS"}.get(str(v).upper(),str(v).upper())
by_name=collections.defaultdict(list)
for a in feed:
 if int(a.get("season",0))==2026 and int(a.get("week",0))==8:
  by_name[(norm(a.get("player_display_name")),a.get("position"),team(a.get("team")))].append(a)
focus=[r for r in audit if float(r["actual"])==0]+[{"player":r["player"],"position":r["position"],"team":r["team"],"actual":None} for r in quality["unmatched_rows"]]
report=[]
for r in focus:
 matches=by_name[(norm(r["player"]),r["position"],team(r["team"]))]
 report.append({"player":r["player"],"position":r["position"],"team":r["team"],"actual_ppr":r["actual"],"feed_rows":len(matches),"classification":"UNVERIFIED_ZERO" if r["actual"] is not None else "UNMATCHED","note":"Verify active status, snap participation, injuries and alternate identifiers from game evidence"})
out=base/"week8_sunday_participation_triage.json";out.write_text(json.dumps({"status":"REVIEW_ONLY","rows":report,"warning":"Do not mark zero PPR as DNP without verified participation evidence."},indent=2)+"\n")
print(json.dumps({"status":"GREEN","zero_ppr_needing_participation_review":sum(r["classification"]=="UNVERIFIED_ZERO" for r in report),"unmatched_needing_identity_or_status_review":sum(r["classification"]=="UNMATCHED" for r in report),"priority":sorted(report,key=lambda r:({"Lamar Jackson":0,"Zay Flowers":1,"Tre Tucker":2,"Breece Hall":3}.get(r["player"],10),r["player"]))[:12],"saved":str(out),"production_changed":False},indent=2))
