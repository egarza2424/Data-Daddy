"""Create a review-only injury-opportunity candidate report from verified OUTs.

Does not change projections, Sleeper Scores, or infer a replacement starter.
"""
import argparse
import json
from pathlib import Path

import pandas as pd


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", default="projection-model/validation/starter-absence-evidence.csv")
    parser.add_argument("--verified-outs", default="data/verified_injury_outs.json")
    parser.add_argument("--output", default="projection-model/validation/injury-opportunity-candidates.csv")
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--week", type=int, required=True)
    args = parser.parse_args()

    outs = json.loads(Path(args.verified_outs).read_text(encoding="utf-8")).get("out", [])
    evidence = pd.read_csv(args.evidence, dtype={"starter_player_id": str, "beneficiary_sleeper_id": str})
    evidence = evidence.fillna("")
    rows = []
    for starter in outs:
        if int(starter.get("season", -1)) != args.season or int(starter.get("week", -1)) != args.week:
            continue
        # Direct replacement candidates must share the injured player's position.
        # Cross-position target redistribution requires separate evidence and review.
        matches = evidence[
            (evidence["starter_player_id"].astype(str) == str(starter["player_id"]))
            & (evidence["team"].astype(str) == str(starter["team"]))
            & (evidence["position"].astype(str) == str(starter["position"]))
        ].copy()
        matches["candidate_opportunities"] = (
            pd.to_numeric(matches["recent_targets"], errors="coerce").fillna(0)
            + pd.to_numeric(matches["recent_carries"], errors="coerce").fillna(0)
        )
        matches = matches.sort_values("candidate_opportunities", ascending=False)
        if matches.empty:
            rows.append({
                "season": args.season, "week": args.week,
                "injured_starter": starter["player_name"], "team": starter["team"],
                "starter_status": starter["status"], "injury_source": starter.get("source", ""),
                "candidate_name": "", "candidate_position": "",
                "candidate_sleeper_id": "", "identity_match_status": "NO_EVIDENCE",
                "prior_week_targets": "", "prior_week_carries": "",
                "baseline_targets_per_game": "", "baseline_carries_per_game": "",
                "recent_rush_share_pct": "", "prior_week_opportunities": "",
                "starter_played_recent_week": "", "role_confidence": "UNKNOWN",
                "opportunity_status": "REVIEW_REQUIRED_NO_CANDIDATE",
                "projected_workload": "", "approved_for_scoring": False,
            })
        for _, candidate in matches.iterrows():
            # Same-team participation is not proof of replacement hierarchy.
            # Starter OUT is verified, but beneficiary workload is unconfirmed.
            rows.append({
                "season": args.season, "week": args.week,
                "injured_starter": starter["player_name"], "team": starter["team"],
                "starter_status": starter["status"], "injury_source": starter.get("source", ""),
                "candidate_name": candidate["beneficiary_name"],
                "candidate_position": candidate["position"],
                "candidate_sleeper_id": candidate["beneficiary_sleeper_id"],
                "identity_match_status": candidate["identity_match_status"],
                "prior_week_targets": candidate["recent_targets"],
                "prior_week_carries": candidate["recent_carries"],
                "baseline_targets_per_game": candidate["baseline_targets_per_game"],
                "baseline_carries_per_game": candidate["baseline_carries_per_game"],
                "recent_rush_share_pct": candidate["recent_rush_share_pct"],
                "prior_week_opportunities": candidate["candidate_opportunities"],
                "starter_played_recent_week": candidate["starter_played_recent_week"],
                "role_confidence": "UNCONFIRMED",
                "opportunity_status": "REVIEW_REQUIRED_ROLE_UNCONFIRMED",
                "projected_workload": "", "approved_for_scoring": False,
            })

    columns = [
        "season", "week", "injured_starter", "team", "starter_status",
        "injury_source", "candidate_name", "candidate_position",
        "candidate_sleeper_id", "identity_match_status",
        "prior_week_targets", "prior_week_carries", "baseline_targets_per_game",
        "baseline_carries_per_game", "recent_rush_share_pct",
        "prior_week_opportunities", "starter_played_recent_week",
        "role_confidence", "opportunity_status", "projected_workload",
        "approved_for_scoring",
    ]
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(output, index=False)
    print(f"Saved {len(rows)} review-only injury-opportunity candidates to {output}")
    print("No projections or sleeper scores changed.")


if __name__ == "__main__":
    main()
