
import json
from collections import defaultdict

with open("nfl-stats.json", encoding="utf-8") as file:
    stats = json.load(file)

with open(
    "data/red_zone_usage_2026_week6.json",
    encoding="utf-8",
) as file:
    feed = json.load(file)

history = defaultdict(dict)

for row in stats.get("players", []):
    try:
        season = int(row.get("season", 0))
        week = int(row.get("week", 0))
    except (ValueError, TypeError):
        continue

    if season != 2026 or not 1 <= week < 6:
        continue

    pid = str(row.get("player_id") or "").strip()
    team = str(
        row.get("team") or row.get("recent_team") or ""
    ).strip().upper()

    if pid and team:
        history[pid][week] = team

print("WEEK 6 RED-ZONE TEAM-CHANGE AUDIT")
print("=" * 45)

affected = []

for pid, record in feed["players"].items():
    weeks = record.get("weeks_evaluated", [])
    teams = [(week, history[pid].get(week)) for week in weeks]
    distinct = {team for _, team in teams if team}

    if len(distinct) > 1:
        affected.append((pid, record, teams))

for pid, record, teams in affected:
    print(f"\n{record['player_name']} ({pid})")
    print(f"Position: {record['position']}")
    print(f"Feed team: {record['team']}")
    print(f"Weekly teams: {teams}")

print("\n" + "=" * 45)
print(f"Players checked: {len(feed['players'])}")
print(f"Players with multiple teams: {len(affected)}")
print("AUDIT COMPLETE")
