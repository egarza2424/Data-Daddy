
"""Fetch NFL schedule data for inactive-report validation.

This script does not change player projections or availability.
"""

import csv
import io
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SOURCE_URL = (
    "https://github.com/nflverse/nfldata/"
    "raw/refs/heads/master/data/games.csv"
)

OUTPUT = Path("data/nfl_schedule_2026.json")
SEASON = 2026


def main():
    request = urllib.request.Request(
        SOURCE_URL,
        headers={"User-Agent": "Data-Daddy/1.0"},
    )

    with urllib.request.urlopen(
        request, timeout=45
    ) as response:
        content = response.read().decode("utf-8-sig")

    reader = csv.DictReader(io.StringIO(content))

    games = [
        row for row in reader
        if str(row.get("season", "")).strip() == str(SEASON)
    ]

    if not games:
        raise RuntimeError(
            f"No NFL schedule games found for {SEASON}"
        )

    result = {
        "season": SEASON,
        "source_url": SOURCE_URL,
        "retrieved_at_utc": (
            datetime.now(timezone.utc).isoformat()
        ),
        "game_count": len(games),
        "games": games,
        "schedule_verified": False,
    }

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT.write_text(
        json.dumps(result, indent=2) + "\n",
        encoding="utf-8",
    )

    print("Season:", SEASON)
    print("Games retrieved:", len(games))
    print("Saved:", OUTPUT)


if __name__ == "__main__":
    main()
