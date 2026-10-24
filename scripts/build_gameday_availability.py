
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
ACTIVATIONS_PATH = Path("data/verified_roster_activations.json")

UNAVAILABLE = {
    "OUT", "IR", "INJURED_RESERVE", "INJURY_RESERVE",
    "PUP", "INACTIVE", "SUSPENDED", "SUSPENSION",
    "EXEMPT", "EXEMPT_LIST", "RESERVE/EXEMPT",
    "RESERVE_EXEMPT", "NFI",
}



def apply_official_roster_activations(players, checked_at):
    """Correct stale fantasy-feed IR labels only after official team activation.

    Activation to a 53-man roster does NOT establish game-day availability,
    route share, snap count, or a projected fantasy workload.
    """
    if not ACTIVATIONS_PATH.exists():
        return 0

    payload = json.loads(ACTIVATIONS_PATH.read_text(encoding="utf-8"))
    if (payload.get("schema_version") != 1 or payload.get("season") != 2026
            or payload.get("week") != 7
            or not isinstance(payload.get("activated"), list)):
        raise RuntimeError("Invalid verified roster activation schema")

    expires = datetime.fromisoformat(payload["expires_at_utc"].replace("Z", "+00:00"))
    if datetime.fromisoformat(checked_at) > expires:
        return 0  # Week 7 override must never persist into later weeks.

    sources = {
        "MIN": "https://www.vikings.com/",
        "SF": "https://www.49ers.com/",
        "GB": "https://www.packers.com/",
        "HOU": "https://www.houstontexans.com/",
        "DEN": "https://www.denverbroncos.com/",
    }
    seen = set()
    corrected = 0
    for item in payload["activated"]:
        key = str(item.get("player_id", ""))
        team = item.get("team")
        if key in seen or not key or team not in sources:
            raise RuntimeError(f"Duplicate or unsupported official activation: {key}")
        if not str(item.get("source", "")).startswith(sources[team]):
            raise RuntimeError(f"Non-team source for official activation: {key}")
        if item.get("verified_date") != "2026-10-24":
            raise RuntimeError(f"Invalid activation date: {key}")
        player = players.get(key)
        if (not player or player.get("name") != item.get("player_name")
                or player.get("team") != team
                or player.get("position") != item.get("position")):
            raise RuntimeError(f"Activation does not match player directory: {key}")
        seen.add(key)

        injury = str(player.get("injury_status") or "").upper()
        roster = str(player.get("roster_status") or "").upper()
        if injury in {"OUT", "SUSPENDED", "SUSPENSION", "EXEMPT", "PUP", "NFI"}:
            continue  # Roster activation does not supersede other restrictions.
        if injury in {"IR", "INJURED_RESERVE", "INJURY_RESERVE"}:
            player["injury_status"] = None
            corrected += 1
        if roster in {"INACTIVE", "IR", "INJURED_RESERVE", "INJURY_RESERVE"}:
            player["roster_status"] = "ACTIVE"
            corrected += 1
        player["availability"] = "not_confirmed_inactive"
        player["official_roster_activation_verified"] = True
        player["official_roster_activation_source"] = item["source"]
        player["official_inactive_confirmed"] = False

    return corrected

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

    corrected = apply_official_roster_activations(players, checked_at)
    print(f"Verified roster activation field corrections: {corrected}")

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
