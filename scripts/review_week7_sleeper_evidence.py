"""Review-only Week 7 sleeper evidence comparison; never changes live scores.

The live JavaScript Sleeper Score has eligibility filters and player lookups that
cannot be reproduced exactly from the projection CSV. Baseline is therefore a
transparent *proxy*, not a claimed reproduction of production rankings.
"""
import csv
from collections import defaultdict
from pathlib import Path

PROJECTIONS = Path("projection-model/2026-week7-ppr-projections.csv")
INJURIES = Path("projection-model/validation/injury-opportunity-candidates.csv")
OUTPUT = Path("projection-model/validation/week7-sleeper-evidence-review.csv")
CUTOFFS = {"QB": 10, "RB": 18, "WR": 24, "TE": 10}

def number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

def normalize(value, lo, hi):
    return .5 if hi == lo else (value - lo) / (hi - lo)

def main():
    with PROJECTIONS.open(newline="", encoding="utf-8") as f:
        projections = list(csv.DictReader(f))
    with INJURIES.open(newline="", encoding="utf-8") as f:
        injuries = list(csv.DictReader(f))
    evidence = defaultdict(list)
    for row in injuries:
        if row["season"] == "2026" and row["week"] == "7":
            evidence[(row["candidate_name"].casefold(), row["candidate_position"], row["team"])].append(row)

    groups = defaultdict(list)
    for p in projections:
        position = p["position"]
        ppr = number(p["projected_ppr"])
        ai = number(p["model_score"])
        ppr_rank = number(p["projected_position_rank"])
        ai_rank = number(p["position_rank"])
        if position not in CUTOFFS or None in (ppr, ai, ppr_rank, ai_rank):
            continue
        if ppr_rank <= CUTOFFS[position] or ppr_rank <= ai_rank:
            continue
        # Eligibility proxy only: live JS also excludes completed/archived games
        # and applies a stricter TE receiving-role filter.
        groups[position].append((p, ai, ppr, ppr_rank-ai_rank))

    rows = []
    for position, group in groups.items():
        def bounds(i):
            values = [x[i] for x in group]
            return min(values), max(values)
        ab, pb, rb = bounds(1), bounds(2), bounds(3)
        for p, ai, ppr, advantage in group:
            proxy = 100 * (.45 * normalize(ai, *ab) + .35 * normalize(ppr, *pb)
                           + .20 * normalize(advantage, *rb))
            matches = evidence.get((p["player_name"].casefold(), position, p["team"]), [])
            observed = [number(x["observed_individual_opportunity_change"]) for x in matches]
            observed = [x for x in observed if x is not None]
            approved = any(x["approved_for_scoring"].lower() == "true" for x in matches)
            role_confirmed = any(x["role_confidence"] == "CONFIRMED" for x in matches)
            rows.append({
                "season": 2026, "week": 7, "player_name": p["player_name"],
                "position": position, "team": p["team"],
                "baseline_proxy_score": round(proxy, 2),
                "ai_position_rank": p["position_rank"],
                "ppr_position_rank": p["projected_position_rank"],
                "injury_evidence_rows": len(matches),
                "max_observed_opportunity_change": max(observed) if observed else "",
                "role_confirmed": role_confirmed,
                "approved_for_scoring": approved,
                "external_weekly_ppr_rank_verified": False,
                "proposed_30_25_20_10_15_score": "",
                "reason_not_scored": "Unverified external weekly PPR rankings and unconfirmed beneficiary role",
                "live_score_modified": False,
            })
    rows.sort(key=lambda x: -x["baseline_proxy_score"])
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else [
            "season", "week", "player_name", "position", "team", "baseline_proxy_score",
            "ai_position_rank", "ppr_position_rank", "injury_evidence_rows",
            "max_observed_opportunity_change", "role_confirmed",
            "approved_for_scoring", "external_weekly_ppr_rank_verified",
            "proposed_30_25_20_10_15_score", "reason_not_scored", "live_score_modified"
        ])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Review-only candidates: {len(rows)}; with injury evidence: {sum(bool(r['injury_evidence_rows']) for r in rows)}")
    print(f"Saved {OUTPUT}. No live scores, rankings or projections modified.")
    print("Baseline is a CSV proxy, not the exact live JavaScript score.")

if __name__ == "__main__":
    main()
