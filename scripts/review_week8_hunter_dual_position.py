#!/usr/bin/env python3
"""Review-only Hunter dual-position correction in Week 8 frozen accuracy audit.
Do not edit published actuals or projections.
"""
import csv,json,pathlib,statistics
base=pathlib.Path("projection-model/validation")
src=base/"week8_sunday_ppr_frozen_accuracy_review.csv"
rows=list(csv.DictReader(src.open(newline="")))
feed=json.loads(pathlib.Path("data/actual-ppr-2026.json").read_text())["players"]
hunter=[r for r in feed if int(r.get("season",0))==2026 and int(r.get("week",0))==8 and r.get("player_display_name")=="Travis Hunter" and r.get("team") in ("JAX","JAC")]
if len(hunter)!=0:raise SystemExit("Hunter already in published feed; review before applying research correction")
evidence=json.loads((base/"week8_sunday_high_impact_nflverse_evidence.json").read_text())["players"]
found=[r for p in evidence if p["player"]=="Travis Hunter" for r in p["same_team_rows"] if r.get("player_id")=="00-0040718" and r.get("position")=="CB"]
if len(found)!=1:raise SystemExit("No unique Hunter CB-source identity; abort")
if any(r["player"]=="Travis Hunter" for r in rows):raise SystemExit("Hunter already matched")
snapshot=list(csv.DictReader(pathlib.Path("model-snapshots/2026-10-31-pregame-ppr-projections.csv").open(newline="")))
s=[r for r in snapshot if r["player_name"]=="Travis Hunter" and r["position"]=="WR" and r["team"]=="JAX" and int(r["snapshot_week"])==8]
if len(s)!=1:raise SystemExit("No unique Hunter WR snapshot")
actual=float(found[0]["fantasy_points_ppr"]);pred=float(s[0]["projected_ppr"])
row={"player":"Travis Hunter","position":"WR","team":"JAX","projected":round(pred,2),"actual":round(actual,2),"error":round(pred-actual,2),"absolute_error":round(abs(pred-actual),2),"projected_position_rank":s[0]["projected_position_rank"],"model":s[0]["projection_model"]}
updated=rows+[dict((k,str(v)) for k,v in row.items())]
mae=lambda rs:round(statistics.mean(float(r["absolute_error"]) for r in rs),3)
report={"status":"REVIEW_ONLY","source_player_id":"00-0040718","source_position":"CB","fantasy_position":"WR","hunter":row,"before":{"matched":len(rows),"mae":mae(rows)},"after":{"matched":len(updated),"mae":mae(updated)},"wr_before_mae":mae([r for r in rows if r["position"]=="WR"]),"wr_after_mae":mae([r for r in updated if r["position"]=="WR"]),"notes":["Source ID and team matched uniquely; source CB label is not fantasy WR eligibility","Do not modify live feed or model without approval","Monday CHI/SEA excluded"]}
out=base/"week8_sunday_hunter_dual_position_review.json";out.write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report,indent=2))
