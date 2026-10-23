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
    evidence = evidence.astype(object).fillna("")
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
        # Compare the starter's latest observed absence week with their prior
        # active games. This is an observed team-level change, not an allocation.
        absence_week = int(matches["recent_week"].max()) if not matches.empty else None
        observed_position_change = None
        if stats is not None and absence_week is not None:
            starter_absent = not bool(stats[
                (stats["week"] == absence_week)
                & (stats[team_col].astype(str) == str(starter["team"]))
                & (stats["position"].astype(str) == str(starter["position"]))
                & (stats[name_col].astype(str).str.lower().str.replace(r"[^a-z0-9]", "", regex=True)
                   == "".join(c for c in str(starter["player_name"]).lower() if c.isalnum()))
            ].shape[0])
            if starter_absent:
                position_stats = stats[
                    (stats[team_col].astype(str) == str(starter["team"]))
                    & (stats["position"].astype(str) == str(starter["position"]))
                ]
                totals = position_stats.groupby("week")[["targets", carry_col]].sum()
                prior = totals[totals.index < absence_week].tail(4)
                if not prior.empty and absence_week in totals.index:
                    observed_position_change = round(
                        float(totals.loc[absence_week].sum() - prior.sum(axis=1).mean()), 2
                    )
        # Observed beneficiary change versus their own pre-absence baseline.
        # Missing baseline is unknown, not a zero-opportunity assumption.
        def individual_change(candidate):
            if candidate.get("beneficiary_history_status") != "HAS_PRIOR_BASELINE":
                return None
            try:
                recent = float(candidate["candidate_opportunities"])
                baseline = float(candidate["baseline_targets_per_game"]) + float(candidate["baseline_carries_per_game"])
                return round(recent - baseline, 2)
            except (ValueError, TypeError):
                return None

        total_recent = float(matches["candidate_opportunities"].sum())
        # Shares describe observed same-position participation only.
        # Do not convert the starter's full historical volume into a beneficiary
        # workload estimate without evidence for retention and role assignment.
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
                "observed_individual_opportunity_change": None,
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
                "illustrative_vacated_opportunities": None,
                "observed_position_opportunity_change": observed_position_change,
                "observed_individual_opportunity_change": individual_change(candidate),
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
        "observed_position_opportunity_change", "observed_individual_opportunity_change",
        "approved_for_scoring",
    ]
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(output, index=False)
    print(f"Saved {len(rows)} review-only injury-opportunity candidates to {output}")
    print("No projections or sleeper scores changed.")


if __name__ == "__main__":
    main()
