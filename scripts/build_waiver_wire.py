import json
from pathlib import Path

SOURCE = Path("nfl-stats.json")
OWNERSHIP_SOURCE = Path("waiver_wire_ownership.json")
OUTPUT = Path("waiver_wire_candidates.json")

OWNERSHIP_CUTOFF = 65
VALID_PLATFORMS = ("espn", "yahoo", "sleeper")


def load_ownership():
    if not OWNERSHIP_SOURCE.exists():
        print(
            "No verified ownership file found. "
            "Ownership remains pending."
        )
        return {}

    data = json.loads(
        OWNERSHIP_SOURCE.read_text(encoding="utf-8")
    )

    if not isinstance(data, dict):
        raise ValueError(
            "Ownership file must contain a JSON object."
        )

    records = data.get("players", {})

    if not isinstance(records, dict):
        raise ValueError(
            "Ownership players must be a JSON object."
        )

    return records


def verified_ownership(record):
    verified = {}

    if not isinstance(record, dict):
        return verified

    for platform in VALID_PLATFORMS:
        entry = record.get(platform)

        if not isinstance(entry, dict):
            continue

        value = entry.get("percent")
        source = entry.get("source")
        checked_at = entry.get("checked_at")

        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not 0 <= value <= 100
        ):
            continue

        if not (
            isinstance(source, str)
            and source.strip()
            and isinstance(checked_at, str)
            and checked_at.strip()
        ):
            continue

        verified[platform] = {
            "percent": round(float(value), 2),
            "source": source.strip(),
            "checked_at": checked_at.strip(),
        }

    return verified


def ownership_summary(record):
    verified = verified_ownership(record)

    if not verified:
        return {
            "espn_rostered": None,
            "yahoo_rostered": None,
            "sleeper_rostered": None,
            "average_rostered": None,
            "ownership_eligible": None,
            "ownership_sources": {},
            "ownership_source_count": 0,
        }

    average = sum(
        item["percent"] for item in verified.values()
    ) / len(verified)

    return {
        "espn_rostered": (
            verified["espn"]["percent"]
            if "espn" in verified else None
        ),
        "yahoo_rostered": (
            verified["yahoo"]["percent"]
            if "yahoo" in verified else None
        ),
        "sleeper_rostered": (
            verified["sleeper"]["percent"]
            if "sleeper" in verified else None
        ),
        "average_rostered": round(average, 2),
        "ownership_eligible": average < OWNERSHIP_CUTOFF,
        "ownership_sources": verified,
        "ownership_source_count": len(verified),
    }


def main():
    data = json.loads(
        SOURCE.read_text(encoding="utf-8")
    )

    players = data.get("player_lookup", {})
    opportunities = data.get("opportunity_volume", {})
    performances = data.get(
        "recent_player_performance", {}
    )
    red_zone = data.get("red_zone_opportunity", {})
    ownership = load_ownership()

    candidates = []

    for player_id, player in players.items():
        position = player.get("position")

        if position not in {"QB", "RB", "WR", "TE"}:
            continue

        opportunity = opportunities.get(player_id, {})
        games = opportunity.get("games", [])

        current_games = [
            game for game in games
            if int(game.get("season", 0)) == data["season"]
        ]

        current_games.sort(
            key=lambda game: int(game.get("week", 0)),
            reverse=True,
        )

        if not current_games:
            continue

        latest = float(
            current_games[0].get("opportunity_value") or 0
        )

        previous = [
            float(game.get("opportunity_value") or 0)
            for game in current_games[1:4]
        ]

        baseline = (
            sum(previous) / len(previous)
            if previous else None
        )

        change = (
            round(latest - baseline, 2)
            if baseline is not None else None
        )

        performance = performances.get(player_id, {})
        red_zone_data = red_zone.get(player_id, {})

        ownership_data = ownership_summary(
            ownership.get(player_id, {})
        )

        candidates.append({
            "player_id": player_id,
            "name": player.get("name"),
            "team": player.get("team"),
            "position": position,
            "latest_opportunity": latest,
            "previous_opportunity_average": (
                round(baseline, 2)
                if baseline is not None else None
            ),
            "opportunity_change": change,
            "recent_average_ppr": performance.get(
                "average_ppr"
            ),
            "red_zone_score": red_zone_data.get("score"),
            **ownership_data,
            "injury_opportunity": None,
        })

    candidates.sort(
        key=lambda player: (
            player["opportunity_change"] is not None,
            player["opportunity_change"]
            if player["opportunity_change"] is not None
            else float("-inf"),
            player["latest_opportunity"],
        ),
        reverse=True,
    )

    result = {
        "season": data["season"],
        "target_week": data["target_week"],
        "status": "candidates_only",
        "ownership_cutoff": OWNERSHIP_CUTOFF,
        "ownership_rule": "available_verified_average",
        "ownership_minimum_sources": 1,
        "candidates": candidates[:50],
    }

    OUTPUT.write_text(
        json.dumps(result, indent=2) + "\n",
        encoding="utf-8",
    )

    verified_count = sum(
        candidate["ownership_source_count"] > 0
        for candidate in result["candidates"]
    )

    print(
        f"Generated {len(result['candidates'])} "
        "waiver candidates."
    )
    print(
        f"Candidates with verified ownership: "
        f"{verified_count}"
    )
    print(
        "Final waiver recommendations remain pending "
        "verified ownership and injury analysis."
    )


if __name__ == "__main__":
    main()
