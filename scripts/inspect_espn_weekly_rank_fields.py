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

# Examine schema of rank categories without publishing individual player rankings.
ranked = [p for p in rows if isinstance(p, dict) and isinstance(p.get("rankings"), dict)]
for category in sorted({k for p in ranked for k in p["rankings"]}):
    examples = [p["rankings"][category] for p in ranked if category in p["rankings"]]
    sample = examples[0]
    print(f"Ranking category {category}: players={len(examples)}, value_type={type(sample).__name__}")
    if isinstance(sample, dict):
        print("  fields:", sorted(sample.keys()))
        print("  field types:", {k: type(v).__name__ for k, v in sample.items()})
        print("  scoring/period hints:", {k: v for k, v in sample.items()
              if any(term in k.lower() for term in ("period", "season", "type", "date", "week", "source"))})
    elif isinstance(sample, list):
        print("  list length:", len(sample))
        if sample and isinstance(sample[0], dict):
            print("  item fields:", sorted(sample[0].keys()))
print("No rank data exported or used in Sleeper Score.")

# Final classification: summarize ranking types, sources, published flags,
# and representative rank ranges. Never print player names or export ranks.
from collections import defaultdict
groups = defaultdict(list)
for player in ranked:
    for category, entries in player["rankings"].items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            key = (str(category), str(entry.get("rankType")),
                   str(entry.get("rankSourceId")), str(entry.get("published")))
            rank = entry.get("rank")
            if isinstance(rank, (int, float)) and rank > 0:
                groups[key].append(rank)
print("Ranking classifications (category, type, source, published, count, min/max rank):")
for key, values in sorted(groups.items(), key=lambda item: (-len(item[1]), item[0])):
    print(key, "count=", len(values), "range=", min(values), max(values))
print("These records must not be treated as weekly PPR rankings without explicit validation.")
