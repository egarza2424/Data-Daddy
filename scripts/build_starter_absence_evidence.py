"""Build conservative starter-absence candidates from prior-week player usage.

Reads nflverse weekly player statistics and verified OUT statuses. This creates
reviewable evidence, NOT automatic projection uplifts: absent-week target shares
must be established separately before an adjustment is activated.
"""
import argparse
import json
from pathlib import Path
import pandas as pd


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stats", required=True, help="Historical weekly player stats CSV")
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--output", default="projection-model/validation/starter-absence-evidence.csv")
    args = parser.parse_args()
    data = pd.read_csv(args.stats)
    name_col = next((c for c in ("player_display_name", "player_name") if c in data), None)
    team_col = next((c for c in ("recent_team", "team") if c in data), None)
    required = {"season", "week", "position", "targets", "player_id"}
    if not name_col or not team_col or not required.issubset(data.columns):
        raise ValueError("Weekly stats missing player/team/targets columns")
    # Resolve cross-provider identity by normalized player name within team.
    # nflverse IDs and Sleeper IDs are not interchangeable.
    def normalized_name(value):
        import re
        return re.sub(r"[^a-z0-9]", "", str(value).lower().replace("jr.", "").replace("iii", ""))

    data = data[(data.season == args.season) & (data.week < args.week)].copy()
    data = data[data.position.isin(["WR", "TE", "RB"])]
    data["targets"] = pd.to_numeric(data.targets, errors="coerce").fillna(0)
    data["team_targets"] = data.groupby([team_col, "week"])["targets"].transform("sum")
    data["share"] = data.targets.div(data.team_targets.where(data.team_targets > 0)).fillna(0)
    with open("data/verified_injury_outs.json", encoding="utf-8") as handle:
        outs = json.load(handle)["out"]
    # Map nflverse GSIS identifiers to Sleeper IDs when explicitly available.
    # Never silently substitute an nflverse ID as a Sleeper player ID.
    availability = json.loads(Path("data/gameday_availability.json").read_text(encoding="utf-8"))
    gsis_to_sleeper = {}
    for sleeper_id, info in availability.get("players", {}).items():
        gsis = info.get("gsis_id")
        if gsis:
            if gsis in gsis_to_sleeper:
                gsis_to_sleeper[gsis] = None  # ambiguous mapping
            else:
                gsis_to_sleeper[gsis] = str(sleeper_id)
    rows = []
    for starter in outs:
        if starter.get("season") != args.season or starter.get("week") != args.week:
            continue
        team = starter["team"]
        previous = data[data[team_col] == team]
        if previous.empty:
            continue
        last_week = int(previous.week.max())
        last = previous[previous.week == last_week]
        for _, player in last.iterrows():
            if normalized_name(player[name_col]) == normalized_name(starter["player_name"]):
                continue
            earlier = previous[(previous.player_id.astype(str) == str(player.player_id)) & (previous.week < last_week)]
            if earlier.empty:
                continue
            baseline = float(earlier.share.tail(4).mean())
            recent = float(player.share)
            rows.append({
                "season": args.season, "week": args.week,
                "starter_player_id": str(starter["player_id"]),
                "starter_name": starter["player_name"], "team": team,
                "beneficiary_player_id": str(player.player_id),
                "beneficiary_sleeper_id": gsis_to_sleeper.get(str(player.player_id)),
                "identity_match_status": ("GSIS_MATCH" if gsis_to_sleeper.get(str(player.player_id)) else "UNRESOLVED"),
                "beneficiary_name": player[name_col],
                "position": player.position, "recent_week": last_week,
                "baseline_share_pct": round(baseline * 100, 2),
                "recent_share_pct": round(recent * 100, 2),
                "recent_targets": float(player.targets),
                "baseline_games": len(earlier),
                "candidate_uplift_pct": round(max(0, recent / baseline - 1) * 100, 2) if baseline > 0 else 0,
                "activation_status": "REVIEW_REQUIRED",
            })
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=[
        "season", "week", "starter_player_id", "starter_name", "team",
        "beneficiary_player_id", "beneficiary_sleeper_id", "identity_match_status",
        "beneficiary_name", "position", "recent_week",
        "baseline_share_pct", "recent_share_pct", "recent_targets",
        "baseline_games", "candidate_uplift_pct", "activation_status",
    ]).to_csv(out, index=False)
    print(f"Saved {len(rows)} evidence candidates to {out}; no projections changed.")


if __name__ == "__main__":
    main()
