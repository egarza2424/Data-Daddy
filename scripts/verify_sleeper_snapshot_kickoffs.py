#!/usr/bin/env python3
"""Validate a newly captured sleeper snapshot against nflverse scheduled kickoffs."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

EASTERN = ZoneInfo("America/New_York")

def main():
    path = Path(sys.argv[1])
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    schedule = json.loads(Path("data/nfl_schedule_2026.json").read_text(encoding="utf-8"))
    if int(schedule["season"]) != int(snapshot["season"]):
        raise SystemExit("Schedule season mismatch")
    captured = datetime.fromisoformat(snapshot["captured_utc"].replace("Z", "+00:00"))
    if captured.tzinfo is None:
        raise SystemExit("Capture timestamp must be timezone-aware")
    captured = captured.astimezone(timezone.utc)
    games = [g for g in schedule["games"] if int(g["week"]) == int(snapshot["target_week"])]
    if not games:
        raise SystemExit("No scheduled games for snapshot week")
    kickoffs = {}
    for game in games:
        kickoff = datetime.strptime(game["gameday"] + " " + game["gametime"], "%Y-%m-%d %H:%M")
        kickoff = kickoff.replace(tzinfo=EASTERN).astimezone(timezone.utc)
        for team in (game["home_team"], game["away_team"]):
            if team in kickoffs:
                raise SystemExit("Duplicate team game: " + team)
            kickoffs[team] = kickoff
    verified = []
    excluded = []
    for pick in snapshot["picks"]:
        team = str(pick.get("team") or "").upper()
        kickoff = kickoffs.get(team)
        if kickoff is None or captured >= kickoff:
            excluded.append({"player_name": pick.get("player_name"), "team": team,
                             "reason": "missing kickoff" if kickoff is None else "game already started"})
            continue
        if float(pick.get("projected_ppr") or 0) <= 0:
            excluded.append({"player_name": pick.get("player_name"), "team": team,
                             "reason": "missing positive frozen projection"})
            continue
        pick["timing_status"] = "verified_pregame"
        pick["kickoff_utc"] = kickoff.isoformat()
        verified.append(pick)
    if not verified:
        raise SystemExit("No eligible pregame sleeper picks; snapshot not published")
    snapshot["picks"] = verified
    snapshot["timing_status"] = "verified_pregame"
    snapshot["kickoff_source"] = schedule["source_url"]
    snapshot["excluded_at_capture"] = excluded
    path.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    print(f"Verified {len(verified)} pregame picks; excluded {len(excluded)} ineligible picks")

if __name__ == "__main__":
    main()
