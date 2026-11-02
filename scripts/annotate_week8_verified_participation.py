#!/usr/bin/env python3
"""Evidence-backed Week 8 Sunday participation annotations; review-only.
Does not modify model, site, projections or source actuals.
"""
import csv,json,pathlib,statistics
base=pathlib.Path("projection-model/validation")
rows=list(csv.DictReader((base/"week8_sunday_ppr_frozen_accuracy_review.csv").open(newline="")))
quality=json.loads((base/"week8_sunday_actuals_quality_gate_review.json").read_text())
evidence=[
 {"player":"Lamar Jackson","position":"QB","team":"BAL","status":"IN_GAME_INJURY","detail":"Exited after one play with thumb injury","source":"https://www.nbcsports.com/fantasy/football/player-news/2026-11-01/flowers-unable-to-overcome-qb-disaster-vs-bills"},
 {"player":"Zay Flowers","position":"WR","team":"BAL","status":"ACTIVE_ZERO_CONFIRMED","detail":"0 receptions on 5 targets; QB injuries disrupted game","source":"https://www.nbcsports.com/fantasy/football/player-news/2026-11-01/flowers-unable-to-overcome-qb-disaster-vs-bills"},
 {"player":"Tre Tucker","position":"WR","team":"LV","status":"ACTIVE_ZERO_CONFIRMED","detail":"One target, zero receptions in Week 8; genuine zero PPR","source":"https://www.fantasypros.com/nfl/news/617016/tre-tucker-held-without-catch-week-8-win.php"},
 {"player":"Evan Engram","position":"TE","team":"DEN","status":"ACTIVE_ZERO_CONFIRMED","detail":"Three targets, zero receptions in Week 8; genuine zero PPR","source":"https://www.nbcsports.com/fantasy/football/player-news/2026-11-01/engram-goose-egged-in-week-8-win"},
 {"player":"Breece Hall","position":"RB","team":"NYJ","status":"INACTIVE_CONFIRMED","detail":"Officially inactive with quadriceps injury","source":"https://www.newyorkjets.com/news/jets-vs-raiders-nfl-game-inactives-11-1-2026"},
]
lookup={(r["player"],r["position"],r["team"]):r for r in rows}
for e in evidence:
 r=lookup.get((e["player"],e["position"],e["team"]))
 e["matched_in_audit"]=r is not None
 e["projected_ppr"]=float(r["projected"]) if r else None
 e["actual_ppr"]=float(r["actual"]) if r else None
 e["absolute_error"]=float(r["absolute_error"]) if r else None
out=base/"week8_sunday_verified_participation_annotations.json"
out.write_text(json.dumps({"season":2026,"week":8,"status":"REVIEW_ONLY","annotations":evidence,"unverified_zero_count":43,"unmatched_count":len(quality["unmatched_rows"]),"notes":["All original 247 matched rows retained in baseline","In-game injury must be tracked separately, not silently deleted","No automatic changes to scoring, projections, rankings, or models"]},indent=2)+"\n")
print(json.dumps({"status":"GREEN","verified":evidence,"saved":str(out),"production_changed":False},indent=2))
