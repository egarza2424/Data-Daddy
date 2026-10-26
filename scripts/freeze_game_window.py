"""Freeze each game's AI and PPR predictions during the 90-minute inactive-report window.

Never overwrite a captured game. Capture is rejected outside 90-60 minutes
before scheduled kickoff, or if source/schedule evidence is missing.
"""
import csv
import json
import hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path("model-snapshots/game-locks")
AVAILABILITY = Path("data/gameday_availability.json")
INACTIVES = Path("data/nfl_inactive_observations.json")
SCHEDULE = Path("data/nfl_schedule_2026.json")
SOURCE = Path("projection-model")

def normalize(team):
    return {"LAR": "LA", "JAC": "JAX", "WSH": "WAS", "OAK": "LV"}.get(str(team).strip().upper(), str(team).strip().upper())

def main():
    now = datetime.now(timezone.utc)
    schedule = json.loads(SCHEDULE.read_text(encoding="utf-8"))
    locked = 0
    for game in schedule["games"]:
        if str(game.get("season")) not in ("", "2026"):
            continue
        day, clock = str(game.get("gameday", "")), str(game.get("gametime", ""))
        if not day or not clock:
            continue
        if len(clock.split(":")) == 2:
            clock += ":00"
        kickoff = datetime.fromisoformat(f"{day}T{clock}").replace(tzinfo=ZoneInfo("America/New_York")).astimezone(timezone.utc)
        until = kickoff - now
        if not timedelta(minutes=60) <= until <= timedelta(minutes=90):
            continue
        week = int(game["week"])
        home, away = normalize(game["home_team"]), normalize(game["away_team"])
        game_id = f"{day}-{away}-at-{home}"
        folder = ROOT / f"2026-week{week}"
        dest = folder / f"{game_id}.csv"
        meta = folder / f"{game_id}.json"
        if dest.exists() or meta.exists():
            print("Already frozen:", game_id)
            continue
        source = SOURCE / f"2026-week{week}-ppr-projections.csv"
        if not source.exists():
            raise RuntimeError(f"Missing current PPR projections for {game_id}")
        source_age_seconds = now.timestamp() - source.stat().st_mtime
        if not 0 <= source_age_seconds <= 1800:
            raise RuntimeError(
                f"Projection source was not rebuilt recently for {game_id}: "
                f"age={source_age_seconds:.0f}s"
            )
        source_sha256 = hashlib.sha256(source.read_bytes()).hexdigest()
        with source.open(newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        required = {"player_id", "player_name", "position", "team", "position_rank", "projected_ppr", "projected_position_rank", "model_score", "snapshot_week"}
        if not rows or not required.issubset(rows[0]):
            raise RuntimeError(f"Missing AI/PPR fields for {game_id}")
        selected = [row for row in rows if normalize(row["team"]) in {home, away} and str(row["snapshot_week"]) == str(week)]
        if not selected or {normalize(r["team"]) for r in selected} != {home, away}:
            raise RuntimeError(f"Both teams not represented in {game_id}")
        if len({(r["player_id"], r["position"]) for r in selected}) != len(selected):
            raise RuntimeError(f"Duplicate player IDs in {game_id}")
        # Record injury feed freshness; unverified NFL article extractions are
        # never treated as confirmed official inactives.
        freshness = {"status": "missing", "age_minutes": None}
        if AVAILABILITY.exists():
            feed = json.loads(AVAILABILITY.read_text(encoding="utf-8"))
            timestamp = (feed.get("generated_at_utc") or feed.get("checked_at_utc")
                         or feed.get("retrieved_at_utc"))
            if timestamp:
                observed = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
                if observed.tzinfo is not None:
                    age = (now - observed.astimezone(timezone.utc)).total_seconds() / 60
                    freshness = {"status": "fresh" if 0 <= age <= 30 else "stale",
                                 "age_minutes": round(age, 2)}
        official_verified = False
        if INACTIVES.exists():
            report = json.loads(INACTIVES.read_text(encoding="utf-8"))
            official_verified = bool(report.get("official_inactives_verified") is True)
        if freshness["status"] != "fresh":
            raise RuntimeError(f"Refusing game lock with stale/missing availability feed: {game_id} {freshness}")
        # Never silently claim this is a validated inactive feed: the capture
        # records its actual source and time for subsequent provenance checks.
        folder.mkdir(parents=True, exist_ok=True)
        with dest.open("x", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(selected)
        meta.write_text(json.dumps({
            "game_id": game_id, "week": week,
            "home_team": home, "away_team": away,
            "capture_utc": now.isoformat(),
            "kickoff_utc": kickoff.isoformat(),
            "minutes_before_kickoff": round(until.total_seconds() / 60, 2),
            "source": str(source), "players": len(selected),
            "source_sha256": source_sha256,
            "source_age_seconds": round(source_age_seconds, 1),
            "availability_feed": freshness,
            "official_inactives_feed_verified": official_verified,
            "audit_status": "captured_requires_source_and_inactive_verification"
        }, indent=2) + "\n", encoding="utf-8")
        print("Frozen", game_id, len(selected), "players", round(until.total_seconds()/60), "minutes pre-kickoff")
        locked += 1
    print("New game locks:", locked)

if __name__ == "__main__":
    main()
