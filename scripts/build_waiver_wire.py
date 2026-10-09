
import json
from pathlib import Path

SOURCE = Path("nfl-stats.json")
OUTPUT = Path("waiver_wire_candidates.json")


def main():
    data = json.loads(SOURCE.read_text(encoding="utf-8"))

    players = data.get("player_lookup", {})
    opportunities = data.get("opportunity_volume", {})
    performances = data.get("recent_player_performance", {})
    red_zone = data.get("red_zone_opportunity", {})

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
            "espn_rostered": None,
            "yahoo_rostered": None,
            "sleeper_rostered": None,
            "average_rostered": None,
            "ownership_eligible": None,
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
        "ownership_cutoff": 65,
        "ownership_rule": "three_platform_average",
        "candidates": candidates[:50],
    }

    OUTPUT.write_text(
        json.dumps(result, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        f"Generated {len(result['candidates'])} "
        "waiver candidates."
    )
    print(
        "Ownership eligibility and injury opportunity "
        "remain pending verified data."
    )


if __name__ == "__main__":
    main()
