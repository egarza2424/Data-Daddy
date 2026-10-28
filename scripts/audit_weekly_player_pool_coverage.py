"""Read-only weekly player-pool coverage check; never modifies rankings.

Usage: python scripts/audit_weekly_player_pool_coverage.py --week 8
Compares published projections with Sleeper availability and review-only
injury-opportunity candidates. Missing names are review flags, not evidence
of eligibility or grounds for automated inclusion.
"""
import argparse
import csv
import json
import re
from pathlib import Path

POSITIONS = {"QB", "RB", "WR", "TE"}
UNAVAILABLE = {"OUT", "IR", "INJURED_RESERVE", "SUSPENDED", "PUP",
               "PHYSICALLY_UNABLE_TO_PERFORM", "INACTIVE", "RESERVE/EXEMPT"}


def norm(value):
    value = re.sub(r"\s+(jr\.?|sr\.?|ii|iii|iv|v)$", "", str(value or "").lower().strip())
    return re.sub(r"[^a-z0-9]", "", value)


def key(name, position, team):
    team = {"JAC": "JAX", "LA": "LAR", "WSH": "WAS"}.get(str(team or "").upper(), str(team or "").upper())
    return (norm(name), str(position or "").upper(), team)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--week", type=int, required=True)
    args = parser.parse_args()
    if not 1 <= args.week <= 18:
        parser.error("--week must be 1 through 18")
    source = Path(f"projection-model/2026-week{args.week}-ppr-projections.csv")
    with source.open(newline="", encoding="utf-8") as handle:
        projected = list(csv.DictReader(handle))
    if not projected:
        raise SystemExit("Empty published projection file")
    projection_ids = {str(r["player_id"]).strip() for r in projected}
    projection_keys = {key(r["player_name"], r["position"], r["team"]) for r in projected}
    with Path("data/gameday_availability.json").open(encoding="utf-8") as handle:
        availability = json.load(handle)
    rows = []
    # The availability directory is a fantasy-feed directory, not an
    # authoritative active roster. It can contain retired players and
    # backups with stale ACTIVE metadata. Do not label all such players
    # as missing projection coverage. Only evidence-backed candidates
    # below should be flagged for human review.
    directory_count = sum(
        str(player.get("position") or "").upper() in POSITIONS
        for player in availability.get("players", {}).values()
    )
    print(f"Availability directory: {directory_count} skill-position records "
          "(context only; not an active-roster eligibility source)")
    candidates = Path("projection-model/validation/injury-opportunity-candidates.csv")
    if candidates.exists():
        with candidates.open(newline="", encoding="utf-8") as handle:
            for candidate in csv.DictReader(handle):
                if str(candidate.get("week")) != str(args.week):
                    continue
                name = candidate.get("candidate_name") or ""
                position = (candidate.get("candidate_position") or "").upper()
                team = candidate.get("team") or ""
                pid = str(candidate.get("candidate_sleeper_id") or "")
                if position not in POSITIONS or not name:
                    continue
                if pid in projection_ids or key(name, position, team) in projection_keys:
                    continue
                rows.append({"week": args.week, "source": "injury_opportunity_review",
                             "player_name": name, "position": position, "team": team,
                             "player_id": pid, "reason": "INJURY_OPPORTUNITY_CANDIDATE_MISSING_PROJECTION",
                             "context": f"status={candidate.get('opportunity_status', '')}; approved={candidate.get('approved_for_scoring', '')}"})
    rows.sort(key=lambda r: (r["position"], r["player_name"], r["source"]))
    print(f"Week {args.week}: {len(projected)} projected players; {len(rows)} coverage review flags")
    for row in rows:
        print(f"{row['position']:2} {row['player_name'][:27]:27} {row['team']:3} {row['reason']}")
    print("READ ONLY: roster feed is not official; missing projection does not establish a legitimate role.")
    print("No scores, ranks, projections, or eligibility files were changed.")


if __name__ == "__main__":
    main()
