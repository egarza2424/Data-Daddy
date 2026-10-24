"""Read-only audit of eight three-way sleeper disagreements against DD projection signals.
Manual rankings are a user-provided snapshot. This is not a live injury or usage verification.
"""
import csv
from pathlib import Path

P=Path("projection-model/2026-week7-ppr-projections.csv")
NAMES=["Jaylin Noel","Ryan Flournoy","Braelon Allen","Colby Parkinson","Darnell Washington","Malik Willis","Emanuel Wilson","Michael Mayer"]
FIELDS=["projected_ppr","opportunity_score","production_score","usage_score","redzone_score","matchup_score","scoring_environment_score","model_confidence_score"]
def main():
    with P.open(newline="",encoding="utf-8") as f: players=list(csv.DictReader(f))
    print("THREE-WAY SLEEPER OPPORTUNITY SIGNAL AUDIT — READ ONLY")
    for name in NAMES:
        matches=[p for p in players if p["player_name"].casefold()==name.casefold()]
        if not matches:
            print("MISSING:",name);continue
        p=matches[0]
        print(f"\\n{name} | {p['position']} {p['team']} vs {p['opponent']} | AI rank {p['position_rank']} | PPR rank {p['projected_position_rank']} | status {p['roster_status']} / {p['injury_status'] or 'none recorded'}")
        print(" | ".join(f"{key}={p.get(key,'')}" for key in FIELDS))
        print("Review required: depth-chart opportunity, expected touches/routes, injury availability, and signal freshness.")
    print("\\nNo live model, projections, rankings, or sleeper scores changed.")
if __name__=="__main__":main()
