#!/usr/bin/env python3
"""Read-only Week 8 V1 vs experimental sack+INT challenger; injury flags are context only."""
import csv,json,pathlib
root=pathlib.Path("projection-model/validation")
paths={"v1":root/"dst_2026_week8_v1_review_only.csv",
       "risk":root/"dst_2026_week8_opponent_risk_review.csv",
       "injury":root/"dst_2026_week8_qb_ol_audit_review.json"}
missing=[str(p) for p in paths.values() if not p.exists()]
if missing:raise SystemExit("Missing review-only inputs: "+", ".join(missing)+". Run the preview and audits first.")
def load(path):
 with path.open(newline="") as f:return list(csv.DictReader(f))
v1=load(paths["v1"]);risk=load(paths["risk"])
injury=json.loads(paths["injury"].read_text())
if len(v1)!=26 or len(risk)!=26 or len(injury["defenses"])!=26:
 raise SystemExit("Expected 26 defenses in each review-only input")
byrisk={r["defense"]:r for r in risk}
byinj={r["defense"]:r for r in injury["defenses"]}
if len(byrisk)!=26 or len(byinj)!=26:raise SystemExit("Duplicate defense in audit inputs")
# All 26 opponent offenses occur exactly once across the 13 games.
total_dropbacks=sum(int(r["opponent_dropbacks"]) for r in risk)
if total_dropbacks<=0:raise SystemExit("Missing dropback samples")
# Approximate historical league reference rates by summing reported per-game counts,
# which are rounded in the audit. This approximation is explicitly disclosed.
league_sack=sum(float(r["opponent_sack_rate_pct"])*int(r["opponent_dropbacks"]) for r in risk)/total_dropbacks
league_int=sum(float(r["opponent_interceptions_per_game"])*int(r["opponent_games"]) for r in risk)/total_dropbacks*100
out=[]
for row in v1:
 d=row["defense"]
 if d not in byrisk or d not in byinj:raise SystemExit("Unmatched defense "+d)
 r=byrisk[d];i=byinj[d]
 if r["opponent_offense"]!=row["opponent"] or i["opponent_offense"]!=row["opponent"]:
  raise SystemExit("Opponent mismatch for "+d)
 n=int(r["opponent_dropbacks"])
 sack_pct=float(r["opponent_sack_rate_pct"])
 int_pct=100*float(r["opponent_interceptions_per_game"])*int(r["opponent_games"])/n
 shrunk_sack=(n*sack_pct+150*league_sack)/(n+150)
 shrunk_int=(n*int_pct+150*league_int)/(n+150)
 base=float(row["projected_dst_points"])
 delta=0.15*(shrunk_sack-league_sack)+0.30*(shrunk_int-league_int)
 flags="; ".join(f"{x['player']} ({x['position']} {x['game_status']})" for x in i["opponent_ol_designations"])
 qbs="; ".join(f"{x['player']} ({x['status']})" for x in i["opponent_qb_updates"])
 out.append({"defense":d,"opponent":row["opponent"],"home":row["home"],
  "v1_rank":int(row["rank"]),"v1_points":round(base,3),
  "experimental_v2_points":round(base+delta,3),
  "delta_points":round(delta,3),
  "opponent_sack_rate_pct":sack_pct,
  "opponent_int_rate_pct":round(int_pct,3),
  "ol_injury_flags":flags or "NONE_LISTED_IN_SNAPSHOT",
  "qb_context":qbs or "NOT_VERIFIED",
  "injury_source_status":i["source_status"],"status":"REVIEW_ONLY"})
out.sort(key=lambda r:(-r["experimental_v2_points"],r["defense"]))
for j,r in enumerate(out,1):
 r["experimental_v2_rank"]=j
 r["rank_change_up"]=r["v1_rank"]-j
dest=root/"dst_2026_week8_v1_vs_experimental_v2_review.csv"
with dest.open("w",newline="") as f:
 w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
print(json.dumps({"status":"GREEN","week":8,"defenses":len(out),
 "top_15":out[:15],"saved":str(dest),
 "league_reference_sack_rate_pct":round(league_sack,3),
 "league_reference_int_rate_pct":round(league_int,3),
 "notes":["V2 candidate uses historical exploratory 0.15 sack and 0.30 interception coefficients",
 "Reference league rates approximated from rounded 26-opponent audit; NOT identical to historical backtest implementation",
 "Injury designations are context only, no points added or removed",
 "QB status is unverified except where explicitly listed",
 "This is NOT an approved or deployed ranking model"],"production_changed":False},indent=2))
