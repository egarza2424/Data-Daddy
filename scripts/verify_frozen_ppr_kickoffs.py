"""Mark a frozen PPR snapshot verified only when every included team had not kicked off."""
import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

def team(value):
    value = str(value or "").strip().upper()
    return {"LAR": "LA", "JAC": "JAX", "WSH": "WAS", "OAK": "LV"}.get(value, value)

def verify(date):
    base = Path("model-snapshots")
    metadata_path = base / f"{date}-pregame-ppr-projections.json"
    csv_path = base / f"{date}-pregame-ppr-projections.csv"
    if not metadata_path.exists() or not csv_path.exists():
        raise RuntimeError("Missing frozen PPR snapshot and metadata")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    captured = datetime.fromisoformat(metadata["snapshot_utc"].replace("Z", "+00:00"))
    if captured.tzinfo is None:
        raise RuntimeError("Capture timestamp must be timezone-aware")
    week = int(metadata["week"])
    with csv_path.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    if not rows:
        raise RuntimeError("Frozen PPR snapshot is empty")
    schedule = json.loads(Path("data/nfl_schedule_2026.json").read_text(encoding="utf-8"))
    games = [game for game in schedule["games"] if str(game.get("week")) == str(week)]
    kickoffs = {}
    for game in games:
        day = str(game.get("gameday") or game.get("game_date") or "").strip()
        clock = str(game.get("gametime") or game.get("game_time") or "").strip()
        if not day or not clock:
            raise RuntimeError("Schedule missing game date/time")
        if len(clock.split(":")) == 2:
            clock += ":00"
        kickoff = datetime.fromisoformat(f"{day}T{clock}").replace(tzinfo=ZoneInfo("America/New_York")).astimezone(timezone.utc)
        for field in ("home_team", "away_team"):
            club = team(game.get(field))
            if club in kickoffs:
                raise RuntimeError(f"Duplicate schedule team {club}")
            kickoffs[club] = kickoff
    included = {team(row["team"]) for row in rows}
    missing = included - set(kickoffs)
    late = sorted(club for club in included if club in kickoffs and captured >= kickoffs[club])
    if missing or late:
        raise RuntimeError(f"Kickoff verification failed; missing teams={sorted(missing)}, postkickoff teams={late}")
    metadata["audit_status"] = "kickoff_verified"
    metadata["schedule_source"] = schedule.get("source_url")
    metadata["verified_at_utc"] = datetime.now(timezone.utc).isoformat()
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(f"Verified {len(rows)} frozen PPR rows, {len(included)} teams before kickoff")

def verify_ai_snapshot(path):
    """Fail closed: date-only AI captures have no exact time; use end of UTC date."""
    from datetime import timedelta
    path = Path(path)
    date_text = path.name.replace("-pregame-model-snapshot.csv", "")
    captured_upper_bound = datetime.fromisoformat(date_text).replace(tzinfo=timezone.utc) + timedelta(days=1)
    with path.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    if not rows:
        raise RuntimeError("Empty frozen AI snapshot")
    weeks = {str(row.get("snapshot_week", "")).strip() for row in rows}
    if len(weeks) != 1:
        raise RuntimeError("Mixed AI snapshot weeks")
    week = next(iter(weeks))
    schedule = json.loads(Path("data/nfl_schedule_2026.json").read_text(encoding="utf-8"))
    games = [game for game in schedule["games"] if str(game.get("week")) == week]
    kickoffs = {}
    for game in games:
        day = str(game.get("gameday") or "").strip()
        clock = str(game.get("gametime") or "").strip()
        if not day or not clock:
            raise RuntimeError("Missing game kickoff in schedule")
        if len(clock.split(":")) == 2:
            clock += ":00"
        kickoff = datetime.fromisoformat(f"{day}T{clock}").replace(tzinfo=ZoneInfo("America/New_York")).astimezone(timezone.utc)
        for field in ("home_team", "away_team"):
            club = team(game.get(field))
            if club in kickoffs:
                raise RuntimeError("Duplicate team in schedule")
            kickoffs[club] = kickoff
    teams = {team(row.get("team")) for row in rows}
    missing = teams - set(kickoffs)
    late = sorted(t for t in teams if t in kickoffs and captured_upper_bound >= kickoffs[t])
    if missing or late:
        raise RuntimeError(f"AI accuracy blocked: unknown teams={sorted(missing)}; potentially postkickoff teams={late}")
    print(f"AI snapshot eligible: {path}; {len(rows)} rows, {len(teams)} teams")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date")
    parser.add_argument("--ai-snapshot")
    args = parser.parse_args()
    if bool(args.date) == bool(args.ai_snapshot):
        parser.error("Provide exactly one of --date or --ai-snapshot")
    if args.date:
        verify(args.date)
    else:
        verify_ai_snapshot(args.ai_snapshot)
