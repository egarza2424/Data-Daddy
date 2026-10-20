#!/usr/bin/env python3
"""Audit immutable, kickoff-verified DATA DADDY sleeper recommendations.

Only frozen picks with explicit verified_pregame status and recorded actual PPR
can be called hits. Never reconstruct historical picks from live rankings.
"""
import argparse
import csv
import json
from pathlib import Path

THRESHOLDS = {"QB": 16.0, "RB": 10.0, "WR": 10.0, "TE": 8.0}
FIELDS = ["season", "target_week", "player_name", "position", "team", "rank",
          "sleeper_score", "projected_ppr", "actual_ppr", "ppr_lift_pct",
          "timing_status", "result_status", "sleeper_hit", "breakout_hit"]

def norm(value):
    import unicodedata
    value = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(c for c in value.lower() if c.isalnum() and not unicodedata.combining(c))

def audit(snapshot_dir, validation_dir, output):
    results = []
    for path in sorted(snapshot_dir.glob("2026-week*.json")):
        snapshot = json.loads(path.read_text(encoding="utf-8"))
        week = int(snapshot["target_week"])
        report = validation_dir / f"2026-week{week}-validation.csv"
        if not report.exists():
            continue
        with report.open(newline="", encoding="utf-8") as stream:
            actual = list(csv.DictReader(stream))
        grouped = {}
        for row in actual:
            pos = row.get("position", "").upper()
            if pos not in THRESHOLDS: continue
            key = (norm(row.get("player_name")), pos)
            grouped.setdefault(key, []).append(row)
        position_ranks = {}
        for pos in THRESHOLDS:
            values = sorted((float(row["actual_ppr"]) for row in actual
                             if row.get("position") == pos and row.get("actual_ppr") not in ("", None)),
                            reverse=True)
            position_ranks[pos] = values
        for pick in snapshot.get("picks", []):
            pos = str(pick.get("position", "")).upper()
            if pos not in THRESHOLDS: continue
            key = (norm(pick.get("player_name")), pos)
            matches = grouped.get(key, [])
            verified = (snapshot.get("timing_status") == "verified_pregame"
                        and pick.get("timing_status", "verified_pregame") == "verified_pregame")
            status = "not_verified" if not verified else ("recorded_game" if len(matches) == 1 else "unmatched_or_ambiguous")
            actual_ppr = None
            projected = float(pick.get("projected_ppr") or 0)
            if status == "recorded_game":
                actual_ppr = float(matches[0]["actual_ppr"])
            lift = ((actual_ppr / projected - 1) * 100 if actual_ppr is not None and projected > 0 else None)
            hit = bool(status == "recorded_game" and projected > 0 and
                       actual_ppr >= THRESHOLDS[pos] and lift >= 20)
            rank = (1 + sum(value > actual_ppr for value in position_ranks[pos])
                    if actual_ppr is not None else None)
            breakout = bool(hit and rank <= (12 if pos in ("QB", "TE") else 24))
            results.append(dict(season=snapshot.get("season", 2026), target_week=week,
                player_name=pick.get("player_name", ""), position=pos, team=pick.get("team", ""),
                rank=pick.get("rank", ""), sleeper_score=pick.get("sleeper_score", ""),
                projected_ppr=projected, actual_ppr=actual_ppr if actual_ppr is not None else "",
                ppr_lift_pct=round(lift, 1) if lift is not None else "",
                timing_status=snapshot.get("timing_status", "unverified"), result_status=status,
                sleeper_hit=str(hit), breakout_hit=str(breakout)))
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(results)
    print(f"Sleeper audit: {len(results)} frozen picks, {sum(r['sleeper_hit']=='True' for r in results)} verified hits -> {output}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshots", type=Path, default=Path("data/sleeper_snapshots"))
    parser.add_argument("--validation", type=Path, default=Path("model-validation"))
    parser.add_argument("--output", type=Path, default=Path("data/sleeper_validation/sleeper_prediction_audit.csv"))
    args = parser.parse_args()
    audit(args.snapshots, args.validation, args.output)
