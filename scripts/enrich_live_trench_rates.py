#!/usr/bin/env python3
"""Enrich existing live trench records with pregame public team rates.
Does not alter pass_score, run_score, confidence, or model weights.
"""
import argparse
import json
from pathlib import Path
import sys
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from public_trench_signal import compute

FIELDS = (
    "offense_sack_rate", "offense_qb_hit_rate", "offense_rush_success_rate",
    "defense_sack_rate", "defense_qb_hit_rate", "defense_run_stop_rate",
)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stats", default="nfl-stats.json")
    parser.add_argument("--metrics", required=True)
    args = parser.parse_args()
    path = Path(args.stats)
    data = json.loads(path.read_text())
    week = int(data["target_week"])
    existing = data.get("current_trench_signals", {})
    if not existing:
        raise RuntimeError("No existing trench signals: refusing to create or overwrite model output")
    frame = pd.read_csv(args.metrics)
    matches = frame[(frame.season == 2026) & (frame.week == week)]
    if matches.empty:
        raise RuntimeError(f"No strictly pregame metrics for 2026 Week {week}")
    enriched = 0
    rate_records = {}
    for row in matches.to_dict("records"):
        offense = str(row["offense_team"])
        defense = str(row["defense_team"])
        aliases = (offense, "LA" if offense == "LAR" else offense)
        record = next((existing[t] for t in aliases if t in existing), None)
        if not isinstance(record, dict) or record.get("available") is not True:
            continue
        norm = lambda t: "LA" if t == "LAR" else t
        if norm(record.get("defense_team")) != norm(defense):
            continue
        result = compute(row)
        if result.get("available") is not True:
            continue
        for field in FIELDS:
            record[field] = result[field]
        record["rate_source"] = "nflverse 2026 prior-game play-by-play"
        record["offense_history_games"] = int(row["offense_history_games"])
        record["defense_history_games"] = int(row["defense_history_games"])
        rate_records[offense] = {"defense_team": defense, **{field: result[field] for field in FIELDS}, "offense_history_games": int(row["offense_history_games"]), "defense_history_games": int(row["defense_history_games"])}
        enriched += 1
    if enriched == 0:
        raise RuntimeError("No opponent-aligned trench records enriched; refusing empty publication")
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n")
    Path("data/trench-rate-details.json").write_text(json.dumps({"season": 2026, "week": week, "teams": rate_records}, separators=(",", ":")) + "\n")
    print(f"Enriched {enriched} Week {week} trench records; existing scores preserved")

if __name__ == "__main__":
    main()
