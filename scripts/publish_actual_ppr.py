"""Publish actual PPR for completed player-games from nflverse weekly stats."""
import argparse
import csv
import json
from pathlib import Path

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--stats", required=True)
    p.add_argument("--output", default="data/actual-ppr-2026.json")
    a = p.parse_args()
    rows = []
    with open(a.stats, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if str(r.get("season")) != "2026":
                continue
            name = r.get("player_display_name") or r.get("player_name")
            team = r.get("recent_team") or r.get("team")
            position = r.get("position")
            raw = r.get("fantasy_points_ppr")
            if not name or not team or position not in ("QB", "RB", "WR", "TE") or raw in (None, ""):
                continue
            try:
                week = int(r["week"])
                score = round(float(raw), 2)
            except (ValueError, TypeError, KeyError):
                continue
            rows.append({"season": 2026, "week": week, "player_display_name": name,
                         "team": team, "position": position, "fantasy_points_ppr": score})
    # Never overwrite historical predictions; publish actuals independently.
    dest = Path(a.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps({"season": 2026, "players": rows}, separators=(",", ":")) + "\n")
    print("ACTUAL_PPR_PUBLISH: player-game rows=", len(rows),
          "week7_rows=", sum(r["week"] == 7 for r in rows))

if __name__ == "__main__":
    main()
