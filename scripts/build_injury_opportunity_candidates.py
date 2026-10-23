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
    parser.add_argument("--stats", help="Pregame nflverse weekly player statistics for starter workload")
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--week", type=int, required=True)
    args = parser.parse_args()

    outs = json.loads(Path(args.verified_outs).read_text(encoding="utf-8")).get("out", [])
    evidence = pd.read_csv(args.evidence, dtype={"starter_player_id": str, "beneficiary_sleeper_id": str})
    evidence = evidence.fillna("")
    rows = []
    stats = pd.read_csv(args.stats) if args.stats else None
    if stats is not None:
        stats = stats[(stats["season"] == args.season) & (stats["week"] < args.week)].copy()
        name_col = "player_display_name" if "player_display_name" in stats else "player_name"
        team_col = "recent_team" if "recent_team" in stats else "team"
        carry_col = "carries" if "carries" in stats else "rushing_attempts"
        for col in ("targets", carry_col):
            stats[col] = pd.to_numeric(stats[col], errors="coerce").fillna(0)
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
        # Historical starter volume is an upper-bound reference, NOT a guaranteed
        # transferable workload. No automatic uplift or replacement designation.
        starter_targets = None
        starter_carries = None
        if stats is not None:
            history = stats[
                (stats[team_col].astype(str) == str(starter["team"]))
                & (stats["position"].astype(str) == str(starter["position"]))
                & (stats[name_col].astype(str).str.lower().str.replace(r"[^a-z0-9]", "", regex=True)
                   == "".join(c for c in str(starter["player_name"]).lower() if c.isalnum()))
            ].sort_values("week").tail(4)
            if not history.empty:
                starter_targets = round(float(history["targets"].mean()), 2)
                starter_carries = round(float(history[carry_col].mean()), 2)
        total_recent = float(matches["candidate_opportunities"].sum())
        # Allocation shares are historical participation proxies, not projections.
        # A zero-history player remains visible with an unknown allocation.
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
                "starter_played_recent_week": "", "beneficiary_history_status": "UNKNOWN", "role_confidence": "UNKNOWN",
                "opportunity_status": "REVIEW_REQUIRED_NO_CANDIDATE",
                "projected_workload": "", "starter_targets_per_game": starter_targets,
                "starter_carries_per_game": starter_carries,
                "candidate_recent_share_pct": "", "illustrative_vacated_opportunities": "",
                "approved_for_scoring": False,
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
                "beneficiary_history_status": candidate.get("beneficiary_history_status", "UNKNOWN"),
                "starter_played_recent_week": candidate["starter_played_recent_week"],
                "role_confidence": "UNCONFIRMED",
                "opportunity_status": "REVIEW_REQUIRED_ROLE_UNCONFIRMED",
                "projected_workload": "",
                "starter_targets_per_game": starter_targets,
                "starter_carries_per_game": starter_carries,
                "candidate_recent_share_pct": round(100 * float(candidate["candidate_opportunities"]) / total_recent, 2) if total_recent else None,
                "illustrative_vacated_opportunities": round(
                    (starter_targets + starter_carries) * float(candidate["candidate_opportunities"]) / total_recent, 2
                ) if total_recent and starter_targets is not None and starter_carries is not None else None,
                "approved_for_scoring": False,
            })

    columns = [
        "season", "week", "injured_starter", "team", "starter_status",
        "injury_source", "candidate_name", "candidate_position",
        "candidate_sleeper_id", "identity_match_status",
        "prior_week_targets", "prior_week_carries", "baseline_targets_per_game",
        "baseline_carries_per_game", "recent_rush_share_pct",
        "prior_week_opportunities", "beneficiary_history_status", "starter_played_recent_week",
        "role_confidence", "opportunity_status", "projected_workload",
        "starter_targets_per_game", "starter_carries_per_game",
        "candidate_recent_share_pct", "illustrative_vacated_opportunities",
        "approved_for_scoring",
    ]
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(output, index=False)
    print(f"Saved {len(rows)} review-only injury-opportunity candidates to {output}")
    print("No projections or sleeper scores changed.")


if __name__ == "__main__":
    main()
