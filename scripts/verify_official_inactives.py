
"""Verify game-day inactives against reviewed NFL reports.

Does not infer official inactives from fantasy injury feeds.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

INPUT = Path("data/official_inactive_reports.json")
OUTPUT = Path("data/verified_official_inactives.json")


def main():
    now = datetime.now(timezone.utc).isoformat()

    result = {
        "generated_at_utc": now,
        "source_type": "official_nfl_inactive_reports",
        "verification_status": "no_verified_reports",
        "games": [],
        "players": [],
    }

    if INPUT.exists():
        reports = json.loads(INPUT.read_text(encoding="utf-8"))

        if not isinstance(reports, dict):
            raise ValueError("Invalid official reports format")

        verified = []

        for game in reports.get("games", []):
            if not isinstance(game, dict):
                raise ValueError("Invalid game record")

            if not game.get("nfl_source_url"):
                raise ValueError("Missing NFL source URL")

            if not game.get("verified_at_utc"):
                raise ValueError("Missing verification timestamp")

            if not game.get("game_id"):
                raise ValueError("Missing game identifier")

            for player in game.get("inactives", []):
                if not isinstance(player, dict):
                    raise ValueError("Invalid inactive record")

                if not all(
                    player.get(field)
                    for field in ("name", "team", "position")
                ):
                    raise ValueError("Incomplete inactive record")

                verified.append({
                    **player,
                    "game_id": game["game_id"],
                    "source_url": game["nfl_source_url"],
                    "verified_at_utc": game["verified_at_utc"],
                    "official_inactive_confirmed": True,
                })

        result["games"] = reports.get("games", [])
        result["players"] = verified
        result["verification_status"] = (
            "verified_reports_present"
            if verified
            else "no_verified_reports"
        )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(result, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        f"Official inactive records: {len(result['players'])}"
    )
    print(f"Verification: {result['verification_status']}")


if __name__ == "__main__":
    main()
