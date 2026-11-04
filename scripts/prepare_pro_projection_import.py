#!/usr/bin/env python3
"""Prepare (but DO NOT upload) a validated DATA DADDY projection snapshot.

Usage:
  python scripts/prepare_pro_projection_import.py \
    --csv projection-model/2026-week8-ppr-projections.csv \
    --season 2026 --week 8 \
    --output projection-model/validation/pro-week8-import-draft.json

No database access, credentials, network requests, or writes outside --output.
"""
import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

REQUIRED = {
    "snapshot_week", "player_id", "player_name", "position", "team",
    "projected_ppr", "projected_position_rank", "projection_model",
}
POSITIONS = {"QB", "RB", "WR", "TE"}


def prepare(source: Path, season: int, week: int, version: int):
    if version < 1:
        raise ValueError("Snapshot version must be a positive integer")
    raw = source.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    with source.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        missing = REQUIRED - set(reader.fieldnames or [])
        if missing:
            raise ValueError("Missing columns: " + ", ".join(sorted(missing)))
        rows = list(reader)
    if not rows:
        raise ValueError("CSV has no player rows")
    if not (1 <= week <= 22):
        raise ValueError("NFL week must be between 1 and 22")

    players, availability, seen = [], [], set()
    for index, row in enumerate(rows, start=2):
        def required(name):
            value = (row.get(name) or "").strip()
            if not value:
                raise ValueError(f"Row {index}: missing {name}")
            return value

        player_id = required("player_id")
        if player_id in seen:
            raise ValueError(f"Row {index}: duplicate player_id {player_id}")
        seen.add(player_id)
        if int(required("snapshot_week")) != week:
            raise ValueError(f"Row {index}: snapshot_week differs from {week}")
        position = required("position").upper()
        if position not in POSITIONS:
            raise ValueError(f"Row {index}: unsupported position {position}")
        ppr = float(required("projected_ppr"))
        if not math.isfinite(ppr):
            raise ValueError(f"Row {index}: invalid projected_ppr")
        rank = int(required("projected_position_rank"))
        if rank <= 0:
            raise ValueError(f"Row {index}: invalid projected_position_rank")

        players.append({
            "player_id": player_id,
            "player_name": required("player_name"),
            "position": position,
            "team": required("team").upper(),
            "projected_ppr": ppr,
            "projected_position_rank": rank,
            "projection_model": required("projection_model"),
        })
        availability.append({
            "player_id": player_id,
            "injury_status": (row.get("injury_status") or "").strip() or None,
            "roster_status": (row.get("roster_status") or "").strip() or None,
            "availability": None,
            "observed_at": None,
        })

    return {
        "snapshot": {
            "season": season, "week": week, "version": version, "status": "draft",
            "source_csv_sha256": digest,
            "source_file": str(source),
        },
        "players": players,
        "availability": availability,
        "validation": {
            "schema_note": "snapshot.source_csv_sha256 and snapshot.source_file are audit metadata, not columns in the current SQL schema; map source_commit separately on import.",
            "player_count": len(players),
            "availability_count": len(availability),
            "positions": dict(sorted(Counter(p["position"] for p in players).items())),
            "warning": "CSV status only. Game-day availability must be independently reconciled before approval.",
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--season", required=True, type=int)
    parser.add_argument("--week", required=True, type=int)
    parser.add_argument("--version", required=True, type=int)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = prepare(args.csv, args.season, args.week, args.version)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["validation"], indent=2))
    print(f"Prepared draft: {args.output}")
    print("No Supabase data was changed.")


if __name__ == "__main__":
    main()
