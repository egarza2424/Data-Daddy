#!/usr/bin/env python3
"""Finalize review-only Week 9 D/ST editorial order, preserving original V1 projections."""
import csv,pathlib,json
source=pathlib.Path("projection-model/validation/dst_2026_week9_v1_review_only.csv")
if not source.exists():raise SystemExit("Missing local V1 CSV; run python scripts/preview_dst_2026_week9_v1.py")
with source.open(newline="") as f:rows=list(csv.DictReader(f))
official=[("JAX","BAL"),("CIN","ATL"),("CLE","NO"),("DEN","CAR"),("DET","MIA"),("NYJ","KC"),("DAL","IND"),("LA","WAS"),("NYG","PHI"),("HOU","LAC"),("ARI","SEA"),("GB","NE"),("LV","SF"),("TB","CHI"),("BUF","MIN")]
expected={(a,b) for a,b in official}|{(b,a) for a,b in official}
actual={(r["defense"],r["opponent"]) for r in rows}
if len(rows)!=30 or actual!=expected:
 raise SystemExit("Week 9 matchup mismatch: missing="+str(sorted(expected-actual))+" extra="+str(sorted(actual-expected)))
if any(r["defense"] in ("PIT","TEN") for r in rows):raise SystemExit("Bye teams unexpectedly included")
# Editorial top 10 from completed defensive-production review. Ranks 11-30
# preserve original model relative order; this is not a model recalibration.
top=["DEN","NO","CIN","HOU","JAX","TB","CHI","DET","GB","MIN"]
lookup={r["defense"]:r for r in rows}
if len(lookup)!=30 or any(t not in lookup for t in top):raise SystemExit("Missing defense or duplicate team")
rest=sorted((r for r in rows if r["defense"] not in top),key=lambda r:(int(r["rank"]),r["defense"]))
ordered=[lookup[t] for t in top]+rest
out=[]
for i,r in enumerate(ordered,1):
 out.append({"week":9,"editorial_rank":i,"defense":r["defense"],"opponent":r["opponent"],"home":r["home"],"original_model_rank":r["rank"],"original_model_projection":r["projected_dst_points"],"editorial_reason":"TARGETED_REVIEW" if i<=10 else "MODEL_ORDER_PRESERVED","status":"REVIEW_ONLY"})
dest=pathlib.Path("projection-model/validation/dst_2026_week9_editorial_review.csv")
dest.parent.mkdir(parents=True,exist_ok=True)
with dest.open("w",newline="") as f:
 w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
print(json.dumps({"status":"REVIEW_ONLY","verified_games":15,"defenses":30,"bye_teams":["PIT","TEN"],"neutral_site":"CIN vs ATL in Madrid","rankings":out,"saved":str(dest),"production_changed":False,"notes":["Top 10 editorial recommendations only; not approved for publication","Original V1 projections preserved","Ranks 11-30 retain original V1 relative order","QB/injury status still requires game-day recheck","Thursday Jacksonville matchup should be locked before kickoff"]},indent=2))
