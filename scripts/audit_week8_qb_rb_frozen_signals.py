#!/usr/bin/env python3
"""Review-only Week 8 QB/RB miss diagnosis using frozen pregame signals.
Never substitute postgame information for pregame evidence.
"""
import csv,json,pathlib,re
root=pathlib.Path("."); base=root/"projection-model/validation"
audit=list(csv.DictReader((base/"week8_sunday_ppr_frozen_accuracy_review.csv").open(newline="")))
snap=list(csv.DictReader((root/"model-snapshots/2026-10-31-pregame-model-snapshot.csv").open(newline="")))
def norm(s):
 s=re.sub(r"[.'’\\-]","",str(s or "").lower()).strip()
 return re.sub(r"\\s+(jr|sr|ii|iii|iv|v)$","",re.sub(r"\\s+"," ",s))
def team(s):return {"LA":"LAR","JAC":"JAX","WSH":"WAS"}.get(str(s).upper(),str(s).upper())
idx={}
for r in snap:idx.setdefault((norm(r["player_name"]),r["position"],team(r["team"])),[]).append(r)
fields=["roster_status","injury_status","opponent","offensive_play_caller","defensive_play_caller","opportunity_score","production_score","usage_score","redzone_score","risk_score","matchup_score","play_caller_matchup_score","player_vs_defensive_caller_score","scoring_environment_score","implied_team_total","model_score","position_rank"]
result={}
for pos in ("QB","RB"):
 rows=sorted((r for r in audit if r["position"]==pos),key=lambda r:float(r["absolute_error"]),reverse=True)[:12]
 out=[]
 for r in rows:
  hits=idx.get((norm(r["player"]),pos,team(r["team"])),[])
  out.append({"player":r["player"],"team":r["team"],"projected_ppr":float(r["projected"]),"actual_ppr":float(r["actual"]),"error":float(r["error"]),"absolute_error":float(r["absolute_error"]),"frozen_evidence":{k:hits[0].get(k,"") for k in fields} if len(hits)==1 else None,"snapshot_matches":len(hits)})
 result[pos]=out
report={"status":"REVIEW_ONLY","week":8,"source":"2026-10-31 frozen pregame model snapshot","top_misses":result,"limitations":["Signals are pregame model scores, not direct snap counts, teammate-injury records, or documented game-script forecasts.","No causal conclusions from signal values alone.","No weights, live rankings, or projections changed."]}
path=base/"week8_qb_rb_frozen_signal_miss_review.json"
path.write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps({**report,"saved":str(path),"production_changed":False},indent=2))
