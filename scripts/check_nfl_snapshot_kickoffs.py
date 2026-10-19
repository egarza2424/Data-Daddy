
"""Check whether NFL inactive snapshots preceded each kickoff."""

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

SCHEDULE = Path("data/nfl_schedule_2026.json")
SNAPSHOTS = Path("data/nfl_inactive_snapshots")
OUTPUT = Path("data/nfl_snapshot_kickoff_audit.json")

EASTERN = ZoneInfo("America/New_York")


def parse_timestamp(value):
    parsed = datetime.fromisoformat(
        value.replace("Z", "+00:00")
    )
    if parsed.tzinfo is None:
        raise ValueError("Timestamp has no timezone")
    return parsed.astimezone(timezone.utc)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--week", type=int, default=6)
    args = parser.parse_args()

    if args.season != 2026:
        raise SystemExit(
            "Only the 2026 schedule is supported currently"
        )

    schedule = json.loads(
        SCHEDULE.read_text(encoding="utf-8")
    )

    snapshot_paths = sorted(
        SNAPSHOTS.glob("inactives_*.json")
    )

    if not snapshot_paths:
        raise SystemExit("No inactive snapshots found")

    snapshots = []

    for path in snapshot_paths:
        data = json.loads(
            path.read_text(encoding="utf-8")
        )

        if data.get("verification_status") != (
            "extracted_unverified"
        ):
            raise SystemExit(
                f"Unexpected status: {path}"
            )

        snapshots.append({
            "filename": path.name,
            "retrieved_at": parse_timestamp(
                data["retrieved_at_utc"]
            ),
        })

    games = [
        game for game in schedule["games"]
        if int(game["season"]) == args.season
        and int(game["week"]) == args.week
        and date.fromisoformat(
            game["gameday"]
        ).weekday() == 6
    ]

    if not games:
        raise SystemExit("No Sunday games found")

    results = []

    for game in games:
        kickoff_eastern = datetime.strptime(
            f"{game['gameday']} {game['gametime']}",
            "%Y-%m-%d %H:%M",
        ).replace(tzinfo=EASTERN)

        kickoff_utc = kickoff_eastern.astimezone(
            timezone.utc
        )

        observations = []

        for snapshot in snapshots:
            observed_at = snapshot["retrieved_at"]

            seconds_before = (
                kickoff_utc - observed_at
            ).total_seconds()

            observations.append({
                "snapshot": snapshot["filename"],
                "retrieved_at_utc": (
                    observed_at.isoformat()
                ),
                "before_kickoff": seconds_before > 0,
                "minutes_before_kickoff": round(
                    seconds_before / 60, 2
                ),
            })

        eligible = [
            observation
            for observation in observations
            if observation["before_kickoff"]
            and 0 < observation[
                "minutes_before_kickoff"
            ] <= 120
        ]

        result = {
            "game_id": game["game_id"],
            "kickoff_utc": kickoff_utc.isoformat(),
            "has_timely_pregame_observation": bool(
                eligible
            ),
            "official_inactives_verified": False,
            "observations": observations,
        }

        results.append(result)

        print(
            game["game_id"],
            "| Timely pregame observation:",
            bool(eligible),
            "| Official verification: False",
        )

    OUTPUT.parent.mkdir(
        parents=True, exist_ok=True
    )

    OUTPUT.write_text(
        json.dumps({
            "season": args.season,
            "week": args.week,
            "games_checked": len(results),
            "results": results,
        }, indent=2) + "\n",
        encoding="utf-8",
    )

    print("Audit saved:", OUTPUT)


if __name__ == "__main__":
    main()
