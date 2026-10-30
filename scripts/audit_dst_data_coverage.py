#!/usr/bin/env python3
"""Read-only discovery audit for prospective ESPN-style D/ST data.

Usage: python scripts/audit_dst_data_coverage.py [nfl-stats.json]
Prints JSON to stdout; does not modify any data, rankings, or projections.
Field matches are *candidates*, not verified ESPN-scoring events.
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

TEAMS = set("ARI ATL BAL BUF CAR CHI CIN CLE DAL DEN DET GB HOU IND JAX KC LAC LAR LV MIA MIN NE NO NYG NYJ PHI PIT SEA SF TB TEN WAS".split())
ALIASES = {"JAC": "JAX", "LA": "LAR", "WSH": "WAS", "OAK": "LV"}
FIELDS = {
    "sacks": [r"(^|_)sacks?($|_)", r"defense_sacks"],
    "interceptions": [r"interceptions?", r"interception"],
    "fumble_recoveries": [r"fumble_recover", r"fumbles_recovered"],
    "defensive_touchdowns": [r"defensive_?(td|touchdown)", r"def_?(td|touchdown)"],
    "safeties": [r"(^|_)safet(y|ies)($|_)"],
    "blocked_kicks": [r"blocked_?(kick|punt|field_goal|fg)", r"(kick|punt|fg)_?block"],
    "return_touchdowns": [r"(kick|punt)_?return_?(td|touchdown)", r"return_?(td|touchdown)"],
    "points_allowed": [r"points_?allowed", r"opponent_?points", r"points_against"],
}
def norm(value):
    team = str(value or "").upper().strip()
    return ALIASES.get(team, team)

def walk(obj, path="", depth=0):
    if depth > 15:
        return
    if isinstance(obj, dict):
        yield path, obj
        for key, value in obj.items():
            yield from walk(value, (path + "." if path else "") + str(key), depth + 1)
    elif isinstance(obj, list):
        for value in obj[:2500]:
            yield from walk(value, path + "[]", depth + 1)

def main():
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "nfl-stats.json")
    if not path.is_file():
        raise SystemExit(f"Missing input: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    candidates = {name: Counter() for name in FIELDS}
    team_samples = Counter()
    week_samples = Counter()
    for location, obj in walk(data):
        for key, value in obj.items():
            field = str(key).lower()
            full_path = (location + "." if location else "") + str(key)
            for name, patterns in FIELDS.items():
                if any(re.search(pattern, field) for pattern in patterns):
                    candidates[name][full_path] += 1
        team = norm(obj.get("team") or obj.get("defense_team") or obj.get("defteam"))
        if team in TEAMS:
            team_samples[team] += 1
            if obj.get("week") is not None and obj.get("season") is not None:
                week_samples[f"{obj['season']}-W{obj['week']}"] += 1
    report = {
        "audit_type": "read_only_schema_discovery",
        "season": data.get("season") if isinstance(data, dict) else None,
        "target_week": data.get("target_week") if isinstance(data, dict) else None,
        "teams_with_tagged_records": sorted(team_samples),
        "teams_without_tagged_records": sorted(TEAMS - set(team_samples)),
        "season_week_labels_seen": sorted(week_samples),
        "candidate_fields": {
            name: [{"path": path, "occurrences": count} for path, count in counter.most_common(20)]
            for name, counter in candidates.items()
        },
        "warnings": [
            "Candidate fields do not prove complete or correctly attributed defensive events.",
            "Team-tagged records may be offensive/player rows, not D/ST observations.",
            "ESPN points-allowed accounting, scoring settings, and special-teams events require separate verification.",
            "Historical pregame availability and actual D/ST fantasy totals are not established by this audit."
        ]
    }
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
