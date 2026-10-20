
"""Build a game-specific, unverified NFL inactive observation feed."""

import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

SCHEDULE = Path("data/nfl_schedule_2026.json")
SNAPSHOTS = Path("data/nfl_inactive_snapshots")
OUTPUT = Path("data/nfl_inactive_observations.json")

TEAMS = {
    "ARI": "CARDINALS", "ATL": "FALCONS",
    "BAL": "RAVENS", "BUF": "BILLS",
    "CAR": "PANTHERS", "CHI": "BEARS",
    "CIN": "BENGALS", "CLE": "BROWNS",
    "DAL": "COWBOYS", "DEN": "BRONCOS",
    "DET": "LIONS", "GB": "PACKERS",
    "HOU": "TEXANS", "IND": "COLTS",
    "JAX": "JAGUARS", "KC": "CHIEFS",
    "LA": "RAMS", "LAC": "CHARGERS",
    "LV": "RAIDERS", "MIA": "DOLPHINS",
    "MIN": "VIKINGS", "NE": "PATRIOTS",
    "NO": "SAINTS", "NYG": "GIANTS",
    "NYJ": "JETS", "PHI": "EAGLES",
    "PIT": "STEELERS", "SEA": "SEAHAWKS",
    "SF": "49ERS", "TB": "BUCCANEERS",
    "TEN": "TITANS", "WAS": "COMMANDERS",
}


def timestamp(value):
    result = datetime.fromisoformat(
        value.replace("Z", "+00:00")
    )
    if result.tzinfo is None:
        raise ValueError("Timezone required")
    return result.astimezone(timezone.utc)


def main():
    schedule = json.loads(
        SCHEDULE.read_text(encoding="utf-8")
    )

    games = schedule["games"]
    snapshots = []

    for path in sorted(SNAPSHOTS.glob("inactives_*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))

        if data.get("verification_status") != "extracted_unverified":
            continue

        if data.get("pregame_verified") is not False:
            continue

        snapshots.append(data)

    results = []

    for game in games:
        season = int(game["season"])
        week = int(game["week"])

        if season != 2026:
            continue

        kickoff = datetime.strptime(
            game["gameday"] + " " + game["gametime"],
            "%Y-%m-%d %H:%M",
        ).replace(
            tzinfo=ZoneInfo("America/New_York")
        ).astimezone(timezone.utc)

        home = TEAMS.get(game["home_team"])
        away = TEAMS.get(game["away_team"])

        if not home or not away:
            continue

        eligible = []

        for snapshot in snapshots:
            if (
                snapshot.get("season") != season
                or snapshot.get("week") != week
            ):
                continue

            observed = timestamp(snapshot["retrieved_at_utc"])
            minutes = (kickoff - observed).total_seconds() / 60

            if not 0 < minutes <= 120:
                continue

            covered = set(snapshot.get("teams", []))

            if not {home, away}.issubset(covered):
                continue

            eligible.append((observed, snapshot))

        if not eligible:
            continue

        observed, latest = max(eligible, key=lambda item: item[0])

        players = [
            {
                "name": player["name"],
                "team": player["team"],
                "position": player["position"],
                "emergency_third_qb": player.get(
                    "emergency_third_qb", False
                ),
            }
            for player in latest["players"]
            if player["team"] in {home, away}
        ]

        results.append({
            "game_id": game["game_id"],
            "season": season,
            "week": week,
            "kickoff_utc": kickoff.isoformat(),
            "observed_at_utc": observed.isoformat(),
            "minutes_before_kickoff": round(
                (kickoff - observed).total_seconds() / 60, 2
            ),
            "observation_timing": "retrieved_before_kickoff",
            "lineup_decision_window": (
                "late_under_30_minutes" if (kickoff - observed).total_seconds() < 1800
                else "at_least_30_minutes_before_kickoff"
            ),
            "publication_time_verified": False,
            "source_url": latest["source_url"],
            "source_type": "nfl_article_extraction",
            "verification_status": "extracted_unverified",
            "official_inactives_verified": False,
            "players": players,
        })

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    OUTPUT.write_text(
        json.dumps({
            "season": 2026,
            "generated_at_utc": datetime.now(
                timezone.utc
            ).isoformat(),
            "official_inactives_verified": False,
            "games": results,
        }, indent=2) + "\n",
        encoding="utf-8",
    )

    print("Game-specific observations:", len(results))
    for result in results:
        print(
            "OBSERVATION:", result["game_id"],
            "players:", len(result["players"]),
            "minutes_before_kickoff:", result["minutes_before_kickoff"],
            "source:", result["source_url"],
            "publication_time_verified:", result["publication_time_verified"],
            "lineup_decision_window:", result["lineup_decision_window"],
        )
    timing_counts = {
        "at_least_30_minutes_before_kickoff": 0,
        "late_under_30_minutes": 0,
    }
    for result in results:
        timing_counts[result["lineup_decision_window"]] += 1
    print("Lineup timing summary:", timing_counts)
    if timing_counts["late_under_30_minutes"]:
        print(
            "WARNING: Some reports were first captured under 30 minutes "
            "before kickoff; early lineup availability is not assured."
        )
    print("Official verification: False")
    print("Saved:", OUTPUT)


if __name__ == "__main__":
    main()
