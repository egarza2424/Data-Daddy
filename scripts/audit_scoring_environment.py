#!/usr/bin/env python3
"""Read-only validation of published scoring environment, no model changes."""
import json
import math
from pathlib import Path

data = json.loads(Path("nfl-stats.json").read_text())
env = data.get("current_scoring_environment", {})
target_week = int(data.get("target_week") or 0)
aliases = {"LA": "LAR", "JAC": "JAX", "WSH": "WAS"}
def norm(x):
    return aliases.get(str(x or ""), str(x or ""))
issues = []
seen = {}
for team, rec in sorted(env.items()):
    if not isinstance(rec, dict) or rec.get("available") is not True:
        continue
    opponent = norm(rec.get("opponent"))
    week = int(rec.get("week") or 0)
    total = rec.get("game_total")
    spread = rec.get("spread_line")
    implied = rec.get("implied_team_total")
    if any(x is None or isinstance(x, bool) for x in (total, spread, implied)):
        issues.append(f"{team}: missing market value")
        continue
    total, spread, implied = map(float, (total, spread, implied))
    if not all(map(math.isfinite, (total, spread, implied))):
        issues.append(f"{team}: nonfinite market value")
        continue
    # The published spread is game-level (same sign on both team rows).
    # Determine team-specific implied totals using the reciprocal pair below.
    if week != target_week:
        issues.append(f"{team}: week {week} differs from target {target_week}")
    if not opponent:
        issues.append(f"{team}: missing opponent")
    seen[norm(team)] = (opponent, total, spread, implied, rec.get("source"))
    print(f"{team} vs {opponent}: total={total:g}, team_spread={spread:+g}, implied={implied:g}, source={rec.get('source')}")
for team, (opponent, total, spread, implied, source) in seen.items():
    if opponent not in seen:
        issues.append(f"{team}: opponent {opponent} missing available reciprocal market record")
        continue
    back, other_total, other_spread, other_implied, other_source = seen[opponent]
    if back != team:
        issues.append(f"{team}: {opponent} reciprocal opponent is {back}")
    if abs(total-other_total) > 0.11:
        issues.append(f"{team}/{opponent}: conflicting game totals")
    if abs(spread-other_spread) > 0.11:
        issues.append(f"{team}/{opponent}: game-level spreads disagree")
    if abs(abs(implied-other_implied)-abs(spread)) > 0.21:
        issues.append(f"{team}/{opponent}: implied-point difference does not match spread magnitude")
    if abs(implied+other_implied-total) > 0.21:
        issues.append(f"{team}/{opponent}: implied totals do not sum to game total")
print("\nPublished feed metadata:")
for key in ("updated", "updated_at", "generated_at", "snapshot_generated_utc", "source", "season", "target_week"):
    if key in data: print(f"  {key}: {data[key]}")
for team in ("LAR", "LV", "DET", "GB"):
    record = env.get(team) or env.get("LA" if team == "LAR" else team) or {}
    print(f"  {team} metadata:", {k: v for k, v in record.items() if any(term in k.lower() for term in ("source", "time", "date", "updated", "timestamp", "book", "line"))})
print(f"\nChecked {len(seen)} available team entries; {len(issues)} issue(s).")
for issue in issues: print("ISSUE:", issue)
print("Note: this validates internal market arithmetic and reciprocity, not independent sportsbook accuracy.")
if issues: raise SystemExit(1)
