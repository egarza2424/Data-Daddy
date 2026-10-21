"""Audit repeat multi-TE receiving roles from a local nfl-stats.json export.

Usage: python scripts/audit_te_multi_role.py --stats nfl-stats.json
Reports observed shared receiving roles; does NOT claim formation/personnel rates.
"""
import argparse
import json
from collections import defaultdict

p = argparse.ArgumentParser()
p.add_argument("--stats", default="nfl-stats.json")
p.add_argument("--season", type=int, default=2026)
p.add_argument("--through-week", type=int, default=6)
args = p.parse_args()

with open(args.stats, encoding="utf-8") as f:
    data = json.load(f)
if isinstance(data, dict):
    data = next((data[k] for k in ("players", "stats", "data", "rows") if isinstance(data.get(k), list)), [])
if not isinstance(data, list):
    raise SystemExit("Expected a JSON array of player-week rows")

games = defaultdict(list)
for row in data:
    if str(row.get("position", "")).upper() != "TE": continue
    try:
        season, week = int(row.get("season", 0)), int(row.get("week", 0))
    except (ValueError, TypeError): continue
    if season != args.season or not 1 <= week <= args.through_week: continue
    team = row.get("team")
    name = row.get("player_display_name") or row.get("player_name") or row.get("name")
    if not team or not name: continue
    games[(team, week)].append((name, float(row.get("targets") or 0),
        float(row.get("receptions") or 0), float(row.get("receiving_yards") or 0),
        float(row.get("receiving_tds") or 0)))

role = defaultdict(list)
for (team, week), tes in games.items():
    for name, targets, catches, yards, tds in tes:
        if targets >= 3 and any(n != name and t >= 2 for n, t, *_ in tes):
            role[(team, name)].append((week, targets, catches + yards / 10 + tds * 6))

print("TEAM,PLAYER,QUALIFYING_WEEKS,TARGETS_IN_SHARED_ROLE_GAMES,PPR_IN_SHARED_ROLE_GAMES,USAGE_BONUS")
for (team, name), observations in sorted(role.items()):
    weeks = sorted(x[0] for x in observations)
    bonus = 6 if len(weeks) >= 2 else 0
    print(f"{team},{name},{'/'.join(map(str,weeks))},{sum(x[1] for x in observations):.0f},{sum(x[2] for x in observations):.2f},{bonus}")
print("NOTE: This is an observed shared-target proxy, not verified 12/13 personnel usage.")
