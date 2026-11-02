#!/usr/bin/env python3
"""Review-only Week 8 Sunday audit quality gate.
Separate missing player rows, zero PPR and injury flags before model conclusions.
"""
import csv,json,pathlib,collections
base=pathlib.Path("projection-model/validation")
rows=list(csv.DictReader((base/"week8_sunday_ppr_frozen_accuracy_review.csv").open(newline="")))
summary=json.loads((base/"week8_sunday_ppr_frozen_accuracy_review.json").read_text())
zeros=[{"player":r["player"],"position":r["position"],"team":r["team"],"projected":r["projected"],"actual":r["actual"]} for r in rows if float(r["actual"])==0]
missing=summary.get("unmatched",[])
bypos=collections.Counter(r["position"] for r in zeros)
report={"week":8,"status":"REVIEW_ONLY","zero_ppr_matches":len(zeros),"zero_by_position":dict(bypos),"zero_rows":zeros,"unmatched_count":len(missing),"unmatched_rows":missing,"notes":["Zero scores may be genuine or indicate no participation; do not relabel without evidence","Unmatched players excluded from MAE; distinguish DNP, inactive, injured, and missing feed","No live model or site changes"]}
out=base/"week8_sunday_actuals_quality_gate_review.json"
out.write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps({"status":"GREEN","zero_ppr_matches":len(zeros),"zero_by_position":dict(bypos),"zero_examples":zeros[:20],"unmatched_count":len(missing),"unmatched_examples":missing[:25],"saved":str(out),"production_changed":False},indent=2))
