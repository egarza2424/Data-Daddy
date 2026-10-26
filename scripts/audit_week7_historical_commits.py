"""Reconstruct Week 7 PPR pregame coverage from immutable GitHub commits."""
import csv
import io
import json
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

BASE = "https://api.github.com/repos/egarza2424/Data-Daddy"
PATH = "projection-model/2026-week7-ppr-projections.csv"
OUT = Path("model-validation/2026-week7-historical-commit-coverage.json")
ALIASES = {"LAR": "LA", "JAC": "JAX", "WSH": "WAS", "OAK": "LV"}

def get(url, accept="application/vnd.github+json"):
    headers = {"User-Agent": "Data-Daddy-Audit", "Accept": accept}
    if os.getenv("GH_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GH_TOKEN"]
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=40) as response:
        return response.read().decode("utf-8-sig")

def main():
    schedule = json.loads(Path("data/nfl_schedule_2026.json").read_text())
    commits = json.loads(get(BASE + "/commits?path=" + PATH + "&per_page=100"))
    history = []
    for commit in commits:
        stamp = datetime.fromisoformat(commit["commit"]["committer"]["date"].replace("Z", "+00:00"))
        if stamp.year != 2026 or stamp.month != 10:
            continue
        history.append({"sha": commit["sha"], "timestamp": stamp})
    games = []
    for game in schedule["games"]:
        if int(game["week"]) != 7:
            continue
        kickoff = datetime.fromisoformat(game["gameday"] + "T" + game["gametime"]).replace(
            tzinfo=ZoneInfo("America/New_York")).astimezone(timezone.utc)
        eligible = sorted((c for c in history if c["timestamp"] < kickoff),
                          key=lambda c: c["timestamp"], reverse=True)
        chosen = eligible[0] if eligible else None
        teams = {ALIASES.get(game[k], game[k]) for k in ("home_team", "away_team")}
        result = {
            "game_id": game["game_id"],
            "kickoff_utc": kickoff.isoformat(),
            "teams": sorted(teams),
            "historical_commit": chosen["sha"] if chosen else None,
            "commit_utc": chosen["timestamp"].isoformat() if chosen else None,
            "status": "no_prior_commit" if not chosen else "prior_commit_needs_player_coverage",
        }
        if chosen:
            raw = get("https://raw.githubusercontent.com/egarza2424/Data-Daddy/" +
                      chosen["sha"] + "/" + PATH, "text/plain")
            rows = list(csv.DictReader(io.StringIO(raw)))
            present = {ALIASES.get(r.get("team", ""), r.get("team", "")) for r in rows}
            included = [r for r in rows if ALIASES.get(r.get("team", ""), r.get("team", "")) in teams]
            result["players_in_game"] = len(included)
            result["teams_covered"] = sorted(present & teams)
            result["has_ai_rank"] = sum(bool(r.get("position_rank")) for r in included)
            result["has_ppr_projection"] = sum(bool(r.get("projected_ppr")) for r in included)
            result["status"] = ("historical_pregame_candidate" if teams <= present
                                else "partial_team_coverage")
        games.append(result)
        print(result["game_id"], result["status"], result.get("players_in_game", 0),
              result["commit_utc"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"week": 7, "games": games}, indent=2) + "\n")
    print("Saved", OUT)

if __name__ == "__main__":
    main()
