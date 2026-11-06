"""Refresh published 2026 actual full-PPR results without touching projections.

Uses nflverse's weekly player statistics; preserves historical rows if the
upstream feed is temporarily unavailable or incomplete.
"""
import csv
import io
import json
import urllib.request
from pathlib import Path

SOURCE = "https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_2026.csv"
DEST = Path("data/actual-ppr-2026.json")
POSITIONS = {"QB", "RB", "WR", "TE"}


def main():
    existing = json.loads(DEST.read_text(encoding="utf-8"))
    rows = existing.get("players", [])
    if not isinstance(rows, list):
        raise ValueError("Existing actual PPR file has invalid players array")
    with urllib.request.urlopen(SOURCE, timeout=90) as response:
        content = response.read().decode("utf-8-sig")
    incoming = []
    for r in csv.DictReader(io.StringIO(content)):
        if str(r.get("season")) != "2026":
            continue
        name = r.get("player_display_name") or r.get("player_name")
        team = r.get("recent_team") or r.get("team")
        pos = r.get("position")
        score = r.get("fantasy_points_ppr")
        if not name or not team or pos not in POSITIONS or score in (None, ""):
            continue
        try:
            week = int(r["week"])
            points = round(float(score), 2)
        except (ValueError, TypeError, KeyError):
            continue
        if not 1 <= week <= 18:
            continue
        incoming.append(dict(season=2026, week=week,
                             player_display_name=name, team=team,
                             position=pos, fantasy_points_ppr=points))
    if not incoming:
        raise RuntimeError("No valid 2026 actual PPR rows; preserving existing file")
    def key(row):
        return (int(row["season"]), int(row["week"]),
                row["player_display_name"], row["team"], row["position"])
    merged = {key(r): r for r in rows}
    before = len(merged)
    merged.update({key(r): r for r in incoming})
    result = sorted(merged.values(), key=lambda r: (r["week"], r["team"], r["position"], r["player_display_name"]))
    # Guard against accidental removal of historical scores.
    if len(result) < before:
        raise RuntimeError("Actuals count regressed; refusing to publish")
    output = json.dumps({"season": 2026, "players": result}, separators=(",", ":")) + "\n"
    if DEST.read_text(encoding="utf-8") != output:
        DEST.write_text(output, encoding="utf-8")
    weeks = sorted({r["week"] for r in incoming})
    print(f"Actual PPR: upstream={len(incoming)}, published={len(result)}, weeks={weeks}, latest_week_rows={sum(r['week'] == max(weeks) for r in incoming)}")


if __name__ == "__main__":
    main()
