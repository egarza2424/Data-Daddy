"""Read-only diagnostic: inspect ESPN public player records for weekly expert rank fields.
Prints field names and coverage counts only; never publishes scores or raw records.
"""
import json
import urllib.request
from collections import Counter

URL = ("https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/"
       "seasons/2026/players?scoringPeriodId=7&view=kona_player_info")
filter_data = {"players": {"limit": 2000, "sortPercOwned": {"sortPriority": 1, "sortAsc": False}}}
request = urllib.request.Request(URL, headers={
    "Accept": "application/json",
    "X-Fantasy-Filter": json.dumps(filter_data),
    "User-Agent": "Mozilla/5.0",
})
with urllib.request.urlopen(request, timeout=45) as response:
    rows = json.load(response)
if not isinstance(rows, list) or len(rows) < 500:
    raise RuntimeError("Incomplete ESPN player pool")
print("Player records:", len(rows))
fields = Counter()
for player in rows:
    if isinstance(player, dict):
        fields.update(player.keys())
print("Top-level field coverage:", dict(sorted(fields.items())))
for key in ("rankings", "ranks", "rank", "draftRanksByRankType", "ratings",
            "ownership", "stats", "playerPoolEntry"):
    present = [p.get(key) for p in rows if isinstance(p, dict) and p.get(key) is not None]
    print(f"{key}: {len(present)} records")
    if present:
        sample = present[0]
        if isinstance(sample, dict):
            print("  nested keys:", sorted(sample.keys()))
        elif isinstance(sample, list):
            print("  list length:", len(sample),
                  "first-item keys:", sorted(sample[0].keys()) if sample and isinstance(sample[0], dict) else [])
        else:
            print("  value type:", type(sample).__name__)
print("Diagnostic only: ESPN weekly expert PPR ranks are NOT verified by this run.")
