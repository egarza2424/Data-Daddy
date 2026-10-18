
"""Build a timestamped NFL player availability snapshot.

Sleeper injury statuses are preliminary fantasy-feed data,
not confirmed official NFL game-day inactive announcements.
"""

import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SOURCE_URL = "https://api.sleeper.app/v1/players/nfl"
OUTPUT = Path("data/gameday_availability.json")
POSITIONS = {"QB", "RB", "WR", "TE"}

UNAVAILABLE = {
    "OUT", "IR", "INJURED_RESERVE", "INJURY_RESERVE",
    "PUP", "INACTIVE", "SUSPENDED", "SUSPENSION",
    "EXEMPT", "EXEMPT_LIST", "RESERVE/EXEMPT",
    "RESERVE_EXEMPT", "NFI",
}


def main():
    request = urllib.request.Request(
        SOURCE_URL,
        headers={"User-Agent": "DataDaddy/1.0"},
    )

    with urllib.request.urlopen(request, timeout=60) as response:
        directory = json.load(response)

    if not isinstance(directory, dict) or len(directory) < 1000:
        raise RuntimeError("Incomplete Sleeper player directory.")

    checked_at = datetime.now(timezone.utc).isoformat()
    players = {}

    for sleeper_id, player in directory.items():
        if not isinstance(player, dict):
            continue

        position = str(player.get("position") or "").upper()
        team = str(player.get("team") or "").upper()

        if position not in POSITIONS or not team:
            continue

        injury = str(player.get("injury_status") or "").upper()
        roster = str(player.get("status") or "").upper()

        unavailable = injury in UNAVAILABLE or roster in UNAVAILABLE

        players[str(sleeper_id)] = {
            "player_id": str(sleeper_id),
            "gsis_id": player.get("gsis_id"),
            "name": player.get("full_name"),
            "team": team,
            "position": position,
            "injury_status": injury or None,
            "roster_status": roster or None,
            "availability": (
                "unavailable_reported"
                if unavailable
                else "not_confirmed_inactive"
            ),
            "official_inactive_confirmed": False,
            "source": "Sleeper player directory",
            "checked_at_utc": checked_at,
        }

    if len(players) < 500:
        raise RuntimeError("Too few eligible players returned.")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    snapshot = {
        "season": 2026,
        "generated_at_utc": checked_at,
        "source_url": SOURCE_URL,
        "source_type": "fantasy_feed_not_official_inactives",
        "official_inactives_verified": False,
        "player_count": len(players),
        "players": players,
    }

    OUTPUT.write_text(
        json.dumps(snapshot, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Saved {len(players)} players to {OUTPUT}")


if __name__ == "__main__":
    main()
