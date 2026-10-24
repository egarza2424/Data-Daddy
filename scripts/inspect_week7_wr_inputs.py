"""Read-only WR input integrity checks for Week 7.
Flags disagreements between AI rank, PPR rank, and externally verified availability.
No automatic player boosts, no production mutations.
"""
import csv
from pathlib import Path
P=Path("projection-model/2026-week7-ppr-projections.csv")
FOCUS={"Justin Jefferson","Courtland Sutton"}
def main():
    with P.open(newline="",encoding="utf-8") as f: rows=list(csv.DictReader(f))
    for name in FOCUS:
        p=next(x for x in rows if x["player_name"]==name)
        pos=p["position"]; peers=[x for x in rows if x["position"]==pos]
        ai=int(p["position_rank"]); ppr=int(p["projected_position_rank"])
        comparable=[x for x in peers if abs(float(x["projected_ppr"])-float(p["projected_ppr"]))<=1.5 and x["player_name"]!=name]
        print(f'\n{name}: AI WR{ai} PPR WR{ppr} projected={p["projected_ppr"]} model={p["projection_model"]}')
        for key in ("opportunity_score","production_score","usage_score","redzone_score","model_confidence_score","matchup_score"):
            print(f'  {key}={p[key]}')
        print("  Similar PPR players (AI, PPR, points):")
        for x in sorted(comparable,key=lambda x:abs(float(x["projected_ppr"])-float(p["projected_ppr"])))[:10]:
            print(f'   {x["player_name"]}: {x["position_rank"]}, {x["projected_position_rank"]}, {x["projected_ppr"]}')
        if ai-ppr>=12:print("  ACTION: trace stale/low AI signals vs PPR inputs; no auto-adjustment")
        elif ai>=60 and ppr>=60:print("  ACTION: inspect source targets, receptions, games played, prior-four-game sample and player identity")
    print("\nExternal evidence check (not machine-ingested): Justin Jefferson full practice and cleared Week 7; verify freshness of local features.")
    print("No model, ranking, or projection changed.")
if __name__=="__main__":main()
