"""Review-only injury-opportunity candidates; never changes rankings or projections.

Only measured targets/carries from source are scored. Route share and
teammate injury facts require independently verified evidence, not inference.
"""
import csv
import json
from pathlib import Path

SOURCE = Path("waiver_wire_candidates.json")
OUTPUT = Path("projection-model/validation/2026-week8-injury-opportunity-signal-review.csv")
WATCH = {
    "Antonio Williams": ("Terry McLaurin", "season_ending_confirmed", "WR"),
    "Chig Okonkwo": ("Terry McLaurin", "season_ending_confirmed", "TE"),
}
def num(value):
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None

def main():
    data = json.loads(SOURCE.read_text())
    assert (int(data["season"]), int(data["target_week"])) == (2026, 8)
    by_name = {c["name"]: c for c in data["candidates"]}
    rows = []
    for name, (teammate, status, position) in WATCH.items():
        candidate = by_name.get(name)
        if candidate is None:
            raise RuntimeError(f"Missing eligible candidate: {name}")
        usage = candidate.get("role_usage_evidence") or {}
        history = usage.get("usage_weekly_history") or []
        ordered = sorted(history, key=lambda x: int(x.get("week") or 0))
        metric = "targets" if position in ("WR", "TE") else "carries"
        measured = [(int(g.get("week") or 0), num(g.get(metric))) for g in ordered]
        measured = [(w, v) for w, v in measured if v is not None]
        before = [v for w, v in measured if w < 6]
        after = [v for w, v in measured if w >= 6]
        before_avg = sum(before) / len(before) if before else None
        after_avg = sum(after) / len(after) if after else None
        delta = after_avg - before_avg if before_avg is not None and after_avg is not None else None
        rows.append({
            "player": name, "team": candidate["team"], "position": position,
            "injured_teammate": teammate, "injury_context": status,
            "context_source": "Commanders official announcement 2026-10-20",
            "source_url": "https://www.commanders.com/news/terry-mclaurin-knee-injury-commanders",
            "pre_week6_observed_games": len(before),
            "week6_plus_observed_games": len(after),
            "pre_week6_targets_per_game": round(before_avg, 2) if before_avg is not None else "",
            "week6_plus_targets_per_game": round(after_avg, 2) if after_avg is not None else "",
            "observed_targets_delta": round(delta, 2) if delta is not None else "",
            "pre_injury_route_share": "",
            "post_injury_route_share": "",
            "route_share_source_status": "NOT_IN_SOURCE_NEEDS_PLAY_BY_PLAY_VERIFICATION",
            "injury_opportunity_review": "REVIEW_ONLY_NO_AUTOMATIC_BOOST",
            "preliminary_rank": candidate.get("preliminary_waiver_rank"),
            "waiver_evidence_score": candidate.get("waiver_evidence_score"),
        })
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    for row in rows:
        print(row)
    print(f"Saved {OUTPUT}; no live ranking, projection, or weight changes.")

if __name__ == "__main__":
    main()
