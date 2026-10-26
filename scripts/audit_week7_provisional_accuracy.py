"""Week 7 provisional accuracy using each game's timestamped pre-kickoff GitHub commit.

Never treats provisional result data as final or publishes official accuracy.
"""
import csv
import io
import json
import os
import urllib.request
from collections import defaultdict
from pathlib import Path

BASE = "https://raw.githubusercontent.com/egarza2424/Data-Daddy/"
PATH = "projection-model/2026-week7-ppr-projections.csv"
OUT = Path("model-validation/2026-week7-pregame-provisional-accuracy.json")
ALIASES = {"LAR": "LA", "JAC": "JAX", "WSH": "WAS", "OAK": "LV"}
CUTOFFS = {"QB": 24, "RB": 36, "WR": 36, "TE": 24}

def norm(value):
    return ALIASES.get(value, value)

def fetch(sha):
    url = BASE + sha + "/" + PATH
    headers = {"User-Agent": "Data-Daddy-Audit"}
    if os.getenv("GH_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GH_TOKEN"]
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=40) as response:
        return list(csv.DictReader(io.StringIO(response.read().decode("utf-8-sig"))))

def main():
    coverage = json.loads(Path("model-validation/2026-week7-historical-commit-coverage.json").read_text())
    with Path("model-validation/2026-week7-provisional-validation.csv").open(newline="") as file:
        actuals = {r["player_id"]: r for r in csv.DictReader(file)}
    cache = {}
    predictions = {}
    game_details = []
    for game in coverage["games"]:
        sha = game.get("historical_commit")
        if not sha:
            game_details.append({"game": game["game_id"], "status": "missing_commit"})
            continue
        if sha not in cache:
            cache[sha] = fetch(sha)
        teams = set(game["teams"])
        rows = [r for r in cache[sha] if norm(r.get("team", "")) in teams]
        for r in rows:
            pid = r.get("player_id", "")
            if pid in predictions:
                raise RuntimeError("Player assigned to multiple games: " + pid)
            predictions[pid] = dict(r, game_id=game["game_id"], commit_sha=sha,
                                    captured_utc=game["commit_utc"])
        game_details.append({"game": game["game_id"], "pregame_players": len(rows),
                             "matched_provisional_results": sum(r.get("player_id") in actuals for r in rows),
                             "status": "historical_pregame_candidate"})
    grouped = defaultdict(list)
    unmatched = []
    for pid, prediction in predictions.items():
        actual = actuals.get(pid)
        if actual is None or actual.get("actual_ppr", "") == "":
            unmatched.append({"player_id": pid, "player": prediction.get("player_name"),
                              "game": prediction["game_id"]})
            continue
        if not prediction.get("projected_ppr") or not prediction.get("position_rank"):
            continue
        position = prediction.get("position")
        if position not in CUTOFFS:
            continue
        actual_points = float(actual["actual_ppr"])
        projected = float(prediction["projected_ppr"])
        grouped[position].append({
            "player_id": pid, "player": prediction.get("player_name"),
            "actual_ppr": actual_points, "projected_ppr": projected,
            "error": round(projected - actual_points, 3),
            "ai_rank": int(float(prediction["position_rank"])),
            "ppr_rank": int(float(prediction.get("projected_position_rank") or 9999)),
            "game": prediction["game_id"], "commit_sha": prediction["commit_sha"]
        })
    summary = {}
    for pos, rows in grouped.items():
        n = len(rows)
        summary[pos] = {
            "matched": n,
            "provisional_mae": round(sum(abs(r["error"]) for r in rows) / n, 3),
            "provisional_bias": round(sum(r["error"] for r in rows) / n, 3),
            "largest_misses": sorted(rows, key=lambda r: abs(r["error"]), reverse=True)[:10],
            "ranking_status": "deferred_until_final_results_and_full_cohort"
        }
    # Actual ranks are calculated only within players with provisional results.
    # This avoids claiming that an unfinished week has final NFL-wide ranks.
    for pos, rows in grouped.items():
        ordered = sorted(rows, key=lambda r: (-r["actual_ppr"], r["player_id"]))
        for index, row in enumerate(ordered, 1):
            row["actual_matched_rank"] = index
        cutoff = CUTOFFS[pos]
        top_actual = {r["player_id"] for r in ordered[:cutoff]}
        ranking = {}
        for key, label in (("ai_rank", "ai_score"), ("ppr_rank", "projected_ppr")):
            predicted = sorted(rows, key=lambda r: (r[key], r["player_id"]))
            top_predicted = {r["player_id"] for r in predicted[:cutoff]}
            errors = [abs(r[key] - r["actual_matched_rank"]) for r in rows]
            ranking[label] = {
                "top_n": cutoff,
                "top_n_hits_matched_only": len(top_actual & top_predicted),
                "top_n_denominator_matched_only": min(cutoff, len(rows)),
                "mean_absolute_rank_error_raw_pregame_rank": round(sum(errors) / len(errors), 3),
                "largest_rank_misses": sorted(
                    [{"player": r["player"], "pregame_rank": r[key],
                      "actual_matched_rank": r["actual_matched_rank"],
                      "absolute_rank_error": abs(r[key] - r["actual_matched_rank"])}
                     for r in rows],
                    key=lambda r: r["absolute_rank_error"], reverse=True
                )[:10]
            }
        summary[pos]["ranking"] = ranking
        summary[pos]["ranking_status"] = "provisional_matched_cohort_only"
    result = {
        "week": 7,
        "status": "PROVISIONAL_NOT_FOR_PUBLICATION",
        "source_results": "model-validation/2026-week7-provisional-validation.csv",
        "source_predictions": "per-game historical GitHub commits before kickoff",
        "warning": "Rankings are provisional matched-cohort comparisons only; actual rank is among matched players, and raw pregame ranks can include players not yet matched. Do not publish as final.",
        "games": game_details, "positions": summary,
        "pregame_player_count": len(predictions),
        "matched_provisional_player_count": sum(len(x) for x in grouped.values()),
        "without_provisional_results": len(unmatched),
        "unmatched_examples": unmatched[:20]
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n")
    print("PRELIMINARY ONLY — NOT FINAL ACCURACY")
    print("Pregame players:", len(predictions), "matched:", result["matched_provisional_player_count"])
    for pos in ("QB", "RB", "WR", "TE"):
        if pos in summary:
            print(pos, summary[pos]["matched"], "provisional MAE", summary[pos]["provisional_mae"], "AI hits", summary[pos]["ranking"]["ai_score"]["top_n_hits_matched_only"], "PPR hits", summary[pos]["ranking"]["projected_ppr"]["top_n_hits_matched_only"])
    print("Saved", OUT)

if __name__ == "__main__":
    main()
