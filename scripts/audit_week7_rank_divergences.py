"""Read-only Week 7 AI vs PPR ranking divergence audit. No production changes."""
import csv
from pathlib import Path
P=Path("projection-model/2026-week7-ppr-projections.csv")
WATCH={"Justin Jefferson","Saquon Barkley","Tyjae Spears","Courtland Sutton","Josh Downs","Xavier Worthy","Puka Nacua","DeVonta Smith"}
def main():
    with P.open(newline="",encoding="utf-8") as f: rows=list(csv.DictReader(f))
    print("WEEK 7 RANKING DIVERGENCE AUDIT — READ ONLY")
    for p in rows:
        if p["player_name"] not in WATCH: continue
        ai=int(float(p["position_rank"])); ppr=int(float(p["projected_position_rank"]))
        print(f'{p["player_name"]} | {p["position"]} | AI {ai} | PPR {ppr} | gap {ai-ppr:+d} | projected {float(p["projected_ppr"]):.2f} | injury {p["injury_status"] or "none recorded"}')
        print("  "+" | ".join(f'{k}={p[k]}' for k in ("opportunity_score","production_score","usage_score","redzone_score","model_confidence_score","matchup_score","projection_model")))
        if ai-ppr>=12: print("  FLAG: AI score materially lower than own PPR ranking; review signal freshness and role")
        if p["injury_status"]: print("  FLAG: independently verify game-day availability")
    print("No rankings, projections, or production scores changed.")
if __name__=="__main__": main()
