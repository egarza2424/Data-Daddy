#!/usr/bin/env python3
"""Review-only Week 8 frozen PPR injury sensitivity and high-rank accuracy."""
import csv,json,pathlib,statistics
base=pathlib.Path("projection-model/validation")
rows=list(csv.DictReader((base/"week8_sunday_ppr_frozen_accuracy_review.csv").open(newline="")))
annotations=json.loads((base/"week8_sunday_verified_participation_annotations.json").read_text())
a=annotations.get("annotations",annotations.get("verified",[]))
injured={(r["player"],r["position"],r["team"]) for r in a if r.get("status")=="IN_GAME_INJURY"}
def metric(rs):
 if not rs:return {"n":0,"mae":None,"bias":None}
 return {"n":len(rs),"mae":round(statistics.mean(float(r["absolute_error"]) for r in rs),3),"bias":round(statistics.mean(float(r["error"]) for r in rs),3)}
report={"status":"REVIEW_ONLY","all":metric(rows),"injury_flagged":sorted([{"player":r["player"],"position":r["position"],"error":float(r["absolute_error"])} for r in rows if (r["player"],r["position"],r["team"]) in injured],key=lambda r:-r["error"]),"by_position":{}}
for pos,limit in [("QB",24),("RB",36),("WR",36),("TE",24)]:
 p=[r for r in rows if r["position"]==pos]
 active=[r for r in p if (r["player"],r["position"],r["team"]) not in injured]
 top=[r for r in p if r["projected_position_rank"].isdigit() and int(r["projected_position_rank"])<=limit]
 top_active=[r for r in top if (r["player"],r["position"],r["team"]) not in injured]
 report["by_position"][pos]={"all":metric(p),"excluding_confirmed_in_game_injuries":metric(active),"projected_top_"+str(limit):metric(top),"top_excluding_confirmed_in_game_injuries":metric(top_active)}
report["excluding_confirmed_in_game_injuries"]=metric([r for r in rows if (r["player"],r["position"],r["team"]) not in injured])
report["notes"]=["Confirmed active zero PPR players stay included","Only documented in-game injuries are excluded in sensitivity analysis","Injury-adjusted metrics are diagnostic, not replacement headline MAE","Unmatched players remain excluded; Monday CHI/SEA excluded","No production or model changes"]
out=base/"week8_sunday_injury_sensitivity_review.json"
out.write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps({**report,"saved":str(out),"production_changed":False},indent=2))
