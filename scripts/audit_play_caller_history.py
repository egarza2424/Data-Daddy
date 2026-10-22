#!/usr/bin/env python3
"""Audit historical play-caller evidence without changing live data."""
import json
from collections import Counter
from pathlib import Path

data = json.loads(Path("nfl-stats.json").read_text())
week = data.get("target_week")
print(f"Season={data.get('season')} target_week={week}")
players = data.get("players", [])
print(f"Weekly player rows={len(players)}")
print("Weekly row field examples:", sorted(set().union(*(p.keys() for p in players[:50]))))
for key in ("current_play_caller_signals", "current_player_vs_defensive_caller"):
    collection = data.get(key, {})
    print(f"\n{key}: {len(collection)} entries")
    examples = list(collection.items())[:3]
    for name, item in examples:
        print("Entry:", name, "keys:", sorted(item) if isinstance(item, dict) else type(item).__name__)
        if key == "current_play_caller_signals" and isinstance(item, dict):
            for pos, details in list(item.get("positions", {}).items())[:2]:
                print(" Position:", pos, "keys:", sorted(details))
                print(" Sample:", details.get("sample_size"), "PPR:", details.get("average_ppr"),
                      "game records:", len(details.get("games") or details.get("historical_games") or []))
        elif isinstance(item, dict):
            print(" Sample:", item.get("sample_size"), "PPR:", item.get("average_ppr"),
                  "game records:", len(item.get("games") or item.get("historical_games") or []))
print("\nWeekly play caller fields:", Counter(k for row in players for k in row if "caller" in k))
print("Weekly PPR fields:", Counter(k for row in players for k in row if "ppr" in k.lower() or "fantasy_points" in k.lower()))
print("No player names or sensitive data printed. Audit is read-only.")
