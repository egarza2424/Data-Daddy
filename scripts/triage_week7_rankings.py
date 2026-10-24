"""Read-only Week 7 ranking discrepancy triage with availability review gates."""
import csv
from pathlib import Path
P=Path("projection-model/2026-week7-ppr-projections.csv")
OUT=Path("projection-model/validation/week7-ranking-triage.csv")
EXTERNAL={"Justin Jefferson":5,"Saquon Barkley":14,"Tyjae Spears":34,"Courtland Sutton":38,"Josh Downs":34,"Xavier Worthy":25,"Puka Nacua":56,"DeVonta Smith":58}
def main():
    with P.open(newline="",encoding="utf-8") as f: players={p["player_name"]:p for p in csv.DictReader(f)}
    rows=[]
    for name,external in EXTERNAL.items():
        p=players[name]; ai=int(p["position_rank"]);ppr=int(p["projected_position_rank"])
        injury=p["injury_status"].strip()
        if injury: gate="VERIFY_OFFICIAL_INACTIVES_AND_ROLE"
        elif ai-ppr>=12: gate="INVESTIGATE_AI_SIGNAL_VS_PPR_DIVERGENCE"
        else: gate="INVESTIGATE_OPPORTUNITY_AND_PROJECTION_INPUTS"
        if name=="Justin Jefferson": gate="PRIORITY_REVIEW_WR42_VS_PPR_WR9_AND_CLEARED_STATUS"
        if name=="Courtland Sutton": gate="PRIORITY_REVIEW_AI_AND_PPR_BOTH_WR73"
        rows.append({"player_name":name,"position":p["position"],"ai_rank":ai,"ppr_rank":ppr,"external_snapshot_rank":external,"ai_vs_external_gap":external-ai,"ai_vs_ppr_gap":ai-ppr,"projected_ppr":p["projected_ppr"],"opportunity_score":p["opportunity_score"],"production_score":p["production_score"],"usage_score":p["usage_score"],"redzone_score":p["redzone_score"],"injury_status_snapshot":injury,"review_gate":gate})
    OUT.parent.mkdir(parents=True,exist_ok=True)
    with OUT.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    for r in sorted(rows,key=lambda x:abs(x["ai_vs_external_gap"]),reverse=True):
        print(f'{r["player_name"]}: DD {r["position"]}{r["ai_rank"]}, PPR {r["ppr_rank"]}, screenshot {r["external_snapshot_rank"]}, gap {r["ai_vs_external_gap"]:+d}; {r["review_gate"]}')
    print("Manual screenshot is not independently verified as ESPN. Injury statuses are snapshot only.")
    print("No production rankings or scores changed. Saved",OUT)
if __name__=="__main__":main()
