
"""Save an immutable, unverified NFL inactive observation."""

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

SOURCE = Path("data/nfl_inactives_extracted.json")
SNAPSHOT_DIR = Path("data/nfl_inactive_snapshots")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--week", type=int, required=True)
    args = parser.parse_args()

    if args.season < 2020 or not 1 <= args.week <= 22:
        raise SystemExit("Invalid NFL season or week")

    source = json.loads(SOURCE.read_text(encoding="utf-8"))

    if source.get("verification_status") != "extracted_unverified":
        raise SystemExit("Unexpected source verification status")
    from urllib.parse import urlparse

    source_path = urlparse(source["source_url"]).path.lower()

    # Sunday roundup URLs include the season; primetime URLs may not.
    # Season-less primetime reports remain explicitly unverified and are
    # accepted only in the matching retrieval calendar year.
    is_sunday_season_url = f"{args.season}-season" in source_path
    is_primetime_url = (
        source.get("report_type") == "single_game_primetime"
        and (
            "monday-night-inactives" in source_path
            or "thursday-night-inactives" in source_path
        )
    )
    if f"week-{args.week}-" not in source_path or not (
        is_sunday_season_url or is_primetime_url
    ):
        raise SystemExit("Source URL does not match requested week/report type")
    if is_primetime_url and (
        source.get("expected_team_count") != 2
        or source.get("extracted_team_count") != 2
        or len(source.get("teams", [])) != 2
    ):
        raise SystemExit("Incomplete primetime team coverage")

    
    retrieved_at = datetime.fromisoformat(
        source["retrieved_at_utc"].replace("Z", "+00:00")
    )

    if retrieved_at.tzinfo is None:
        raise SystemExit("Source retrieval time has no timezone")

    now = datetime.now(timezone.utc)
    if is_primetime_url and retrieved_at.year != args.season:
        raise SystemExit("Primetime URL lacks season and retrieval year differs")

    if retrieved_at > now:
        raise SystemExit("Source retrieval time is in the future")

    age_seconds = (now - retrieved_at).total_seconds()

    if age_seconds > 600:
        raise SystemExit("Extraction is older than 10 minutes")

    payload = {
        "season": args.season,
        "week": args.week,
        "snapshot_type": "nfl_article_observation",
        "verification_status": "extracted_unverified",
        "source_url": source["source_url"],
        "retrieved_at_utc": source["retrieved_at_utc"],
        "saved_at_utc": now.isoformat(),
        "player_count": source["player_count"],
        "teams": source["teams"],
        "players": source["players"],
        "schedule_verified": source.get(
            "schedule_verified", False
        ),
        "kickoff_times_verified": source.get(
            "kickoff_times_verified", False
        ),
        "pregame_verified": False,
    }

    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    payload["sha256"] = hashlib.sha256(
        canonical
    ).hexdigest()

    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

    stamp = now.strftime("%Y%m%dT%H%M%S%fZ")
    path = SNAPSHOT_DIR / (
        f"inactives_{args.season}_week_{args.week:02d}_{stamp}.json"
    )

    serialized = json.dumps(
        payload, indent=2, ensure_ascii=False
    ) + "\n"

    try:
        with path.open("x", encoding="utf-8") as output:
            output.write(serialized)
    except FileExistsError:
        raise SystemExit("Snapshot already exists")

    print("Snapshot saved:", path)
    print("Players:", payload["player_count"])
    print("SHA256:", payload["sha256"])
    print("Pregame verified:", payload["pregame_verified"])
    print("Source age seconds:", round(age_seconds, 1))


if __name__ == "__main__":
    main()
