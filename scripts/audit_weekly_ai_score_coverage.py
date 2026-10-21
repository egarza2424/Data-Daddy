"""Audit the current weekly projection universe without inventing live scores.

Live AI scores require browser runtime signals; this checks source coverage and
identity ambiguity, not numeric equality between frozen and live models.
"""
import csv
import re
from collections import Counter
from pathlib import Path

root = Path(__file__).resolve().parents[1]
app = (root / "app.js").read_text(encoding="utf-8")
stats = (root / "nfl-stats.json").read_text(encoding="utf-8")
match = re.search(r'"target_week"\s*:\s*(\d+)', stats)
if not match:
    raise SystemExit("FAIL: target_week missing in nfl-stats.json")
week = int(match.group(1))
path = root / "projection-model" / f"2026-week{week}-ppr-projections.csv"
with path.open(newline="", encoding="utf-8") as stream:
    rows = list(csv.DictReader(stream))
if not rows:
    raise SystemExit("FAIL: empty projection snapshot")

def norm(name):
    name = re.sub(r"[.'’\-]", "", name.lower())
    return re.sub(r"\s+(jr|sr|ii|iii|iv|v)$", "", name).strip()

def team(value):
    return {"LA": "LAR", "JAC": "JAX", "WSH": "WAS"}.get(value, value)

ids = Counter(row["player_id"].strip() for row in rows)
keys = Counter((norm(row["player_name"]), row["position"], team(row["team"])) for row in rows)
problems = []
for row in rows:
    ident = f'{row["player_name"]} ({row["position"]}, {row["team"]}, ID {row["player_id"]})'
    try:
        score = float(row["model_score"])
        ppr = float(row["projected_ppr"])
        assert 0 <= score <= 100 and ppr >= 0
    except (ValueError, TypeError, AssertionError):
        problems.append(f"invalid frozen score/projection: {ident}")
    if ids[row["player_id"].strip()] > 1:
        problems.append(f"duplicate player ID: {ident}")
    if keys[(norm(row["player_name"]), row["position"], team(row["team"]))] > 1:
        problems.append(f"ambiguous normalized identity: {ident}")
    if int(row["snapshot_week"]) != week:
        problems.append(f"wrong snapshot week: {ident}")

checks = {
    "projection universe included after Sleeper/backend merge":
        "weeklyPprProjections.forEach(projection => {" in app and "projectionAdded: true" in app,
    "live scoring is authoritative":
        "function getDisplayedAiScore(player, profile)" in app and
        "return player ? calculateScore(player, profile) : NaN;" in app,
    "projection name lookup checks team":
        "normalizeLookupTeam(player.team) === projectionTeam" in app or
        "normalizeTeam(player.team) === projectionTeam" in app,
}
for label, passed in checks.items():
    print(f'{"PASS" if passed else "FAIL"}: {label}')
    if not passed:
        problems.append(label)
print(f"Week {week}: {len(rows)} projections; {len(ids)} unique IDs; {len(keys)} unique normalized name/position/team keys")
print("Frozen score integrity is NOT a browser live-score coverage test.")
for problem in sorted(set(problems)):
    print("FAIL:", problem)
if problems:
    raise SystemExit(1)
print("PASS: weekly projection identity and frozen score integrity")
