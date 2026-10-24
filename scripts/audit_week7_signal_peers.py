"""Week 7 model-input audit: contrast player signal profiles with same-position peers.
Read-only. This diagnoses outliers, not causes or recommended manual boosts.
"""
import csv
from pathlib import Path
from statistics import median
P=Path("projection-model/2026-week7-ppr-projections.csv")
WATCH=["Justin Jefferson","Courtland Sutton","Tyjae Spears","Josh Downs","Xavier Worthy","Saquon Barkley"]
SIGNALS=["opportunity_score","production_score","usage_score","redzone_score","model_confidence_score","matchup_score"]
def f(row,key):
    try:return float(row[key])
    except (ValueError,TypeError,KeyError):return None
def main():
    with P.open(newline="",encoding="utf-8") as fh: rows=list(csv.DictReader(fh))
    for name in WATCH:
        p=next((r for r in rows if r["player_name"]==name),None)
        if p is None:
            print("MISSING",name);continue
        pos=p["position"]
        peers=[r for r in rows if r["position"]==pos and f(r,"projected_position_rank") is not None and f(r,"projected_position_rank")<=24]
        print(f'\n{name} ({pos}) AI rank {p["position_rank"]}, PPR rank {p["projected_position_rank"]}, PPR {p["projected_ppr"]}, injury {p["injury_status"] or "none recorded"}')
        print("model:",p["projection_model"])
        for key in SIGNALS:
            values=[f(r,key) for r in peers if f(r,key) is not None]
            value=f(p,key)
            if value is not None and values:
                print(f'  {key}: player={value:.1f} | top-24 projected peer median={median(values):.1f} | delta={value-median(values):+.1f}')
        better=sorted((r for r in rows if r["position"]==pos and f(r,"projected_ppr") is not None),key=lambda r:-f(r,"projected_ppr"))
        near=sorted(better,key=lambda r:abs(f(r,"projected_ppr")-f(p,"projected_ppr")))[:6]
        print("closest PPR peers:",", ".join(f'{r["player_name"]} (AI {r["position_rank"]}, PPR {r["projected_position_rank"]})' for r in near))
    print("\nDiagnostic only. Historical signal windows, injury source freshness and true expected usage require separate evidence. No production data changed.")
if __name__=="__main__":main()
