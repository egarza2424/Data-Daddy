"""Audit Week 7 prediction provenance without changing rankings."""
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path("model-snapshots")
SCHEDULE = Path("data/nfl_schedule_2026.json")
OUT = Path("model-validation/2026-week7-pregame-provenance.json")


def run():
    if not SCHEDULE.exists():
        raise SystemExit("Schedule missing: run scripts/fetch_nfl_schedule.py first")
    games = json.loads(SCHEDULE.read_text())["games"]
    results = []
    for game in games:
        if int(game["week"]) != 7:
            continue
        kickoff = datetime.fromisoformat(
            game["gameday"] + "T" + game["gametime"]
        ).replace(tzinfo=ZoneInfo("America/New_York")).astimezone(timezone.utc)
        teams = {game["home_team"], game["away_team"]}
        candidates = []
        for meta in ROOT.glob("*-pregame-ppr-projections.json"):
            info = json.loads(meta.read_text())
            if int(info.get("week", -1)) != 7:
                continue
            captured = datetime.fromisoformat(info["snapshot_utc"].replace("Z", "+00:00"))
            csv_path = meta.with_suffix(".csv")
            if not csv_path.exists() or captured >= kickoff:
                continue
            with csv_path.open(newline="") as handle:
                rows = list(csv.DictReader(handle))
            if not teams.issubset({r["team"] for r in rows}):
                continue
            candidates.append((captured, csv_path, info))
        candidates.sort(key=lambda entry: entry[0], reverse=True)
        selected = candidates[0] if candidates else None
        results.append({
            "game": game.get("game_id"),
            "kickoff_utc": kickoff.isoformat(),
            "status": "pregame_candidate" if selected else "missing_pregame_snapshot",
            "snapshot": str(selected[1]) if selected else None,
            "capture_utc": selected[0].isoformat() if selected else None,
            "audit_status": selected[2].get("audit_status") if selected else None,
        })
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"week": 7, "games": results}, indent=2) + "\n")
    for result in results:
        print(result["game"], result["status"], result["snapshot"])
    print("Saved", OUT)


if __name__ == "__main__":
    run()
