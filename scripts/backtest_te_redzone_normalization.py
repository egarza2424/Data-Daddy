"""Read-only Week 6 TE red-zone normalization sensitivity audit.

Uses frozen Week 6 model_score as baseline proxy, not reconstructed live
browser AI scores. Week 6 red-zone feed must have target_week=6 and use
only weeks before Week 6. Does not modify projections or rankings.
"""
import csv
import json
from pathlib import Path

FEED = Path("data/red_zone_usage_2026_week6.json")
VALID = Path("model-validation/2026-week6-validation.csv")
OUT = Path("model-validation/2026-week6-te-redzone-normalization-audit.csv")
WEIGHT = 0.093  # balanced profile red-zone weight; proxy sensitivity only

feed = json.loads(FEED.read_text(encoding="utf-8"))
assert int(feed["target_week"]) == 6, "Wrong target week"
records = feed["players"]
assert records, "Empty feed"
for record in records.values():
    assert all(int(w) < 6 for w in record.get("weeks_evaluated", [])), "Future leakage"
te_max = max(float(r["weighted_opportunities_per_game"]) for r in records.values() if r["position"] == "TE")
assert te_max > 0
with VALID.open(newline="", encoding="utf-8") as handle:
    validation = list(csv.DictReader(handle))
rows = []
for r in validation:
    if r.get("position") != "TE" or not r.get("actual_ppr") or not r.get("model_score"):
        continue
    pid = str(r.get("player_id") or "")
    rz = records.get(pid)
    if not rz or rz.get("position") != "TE":
        continue
    old = float(rz["red_zone_score"])
    proposed = min(100, round(float(rz["weighted_opportunities_per_game"]) / te_max * 100))
    baseline = float(r["model_score"])
    rows.append(dict(player_id=pid, player=r.get("player_name", rz["player_name"]),
        actual_ppr=float(r["actual_ppr"]), baseline_score=baseline,
        current_redzone=old, proposed_redzone=proposed,
        adjusted_proxy_score=baseline + (proposed-old)*WEIGHT))
if len(rows) < 12:
    raise SystemExit(f"Only {len(rows)} matched TE records; audit insufficient")
actual = sorted(rows, key=lambda x:(-x["actual_ppr"],x["player_id"]))
actual_rank = {x["player_id"]:i+1 for i,x in enumerate(actual)}
actual_top = set(x["player_id"] for x in actual[:24])
def measure(key):
    ranked = sorted(rows,key=lambda x:(-x[key],x["player_id"]))
    ranks = {x["player_id"]:i+1 for i,x in enumerate(ranked)}
    hits = len(set(x["player_id"] for x in ranked[:24]) & actual_top)
    mae = sum(abs(ranks[x["player_id"]]-actual_rank[x["player_id"]]) for x in rows)/len(rows)
    return hits,mae,ranks
before=measure("baseline_score")
after=measure("adjusted_proxy_score")
for r in rows:
    r["baseline_rank"]=before[2][r["player_id"]]
    r["adjusted_rank"]=after[2][r["player_id"]]
    r["actual_rank"]=actual_rank[r["player_id"]]
OUT.parent.mkdir(parents=True,exist_ok=True)
with OUT.open("w",newline="",encoding="utf-8") as handle:
    writer=csv.DictWriter(handle,fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(sorted(rows,key=lambda x:x["baseline_rank"]))
print(f"Matched TEs: {len(rows)}; TE red-zone max: {te_max:.3f}")
print(f"Baseline top-24 hits: {before[0]}; rank MAE: {before[1]:.3f}")
print(f"Adjusted top-24 hits: {after[0]}; rank MAE: {after[1]:.3f}")
print(f"Delta hits: {after[0]-before[0]:+d}; delta rank MAE: {after[1]-before[1]:+.3f}")
print(f"Saved {OUT}")
print("CAUTION: Proxy sensitivity only, not live AI score validation. No production changes.")
