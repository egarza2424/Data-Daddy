#!/usr/bin/env python3
"""Import a validated Pro projection draft into private Supabase tables.

DEFAULT IS READ-ONLY. Requires --apply and SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY.
Never approves snapshots or changes the public website. Requires a JSON draft
from scripts/prepare_pro_projection_import.py.

Note: Supabase REST inserts across three tables are NOT a single transaction.
If a network/database failure occurs, the snapshot can be partially populated;
the script refuses to reuse it. Inspect/reconcile manually before retrying.
"""
import argparse
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path

COLUMNS = {
    "players": {"player_id", "player_name", "position", "team", "projected_ppr", "projected_position_rank", "projection_model"},
    "availability": {"player_id", "injury_status", "roster_status", "availability", "observed_at"},
}


def validate(draft):
    snap = draft["snapshot"]
    season, week, version = (int(snap[k]) for k in ("season", "week", "version"))
    if season < 2020 or not 1 <= week <= 22 or version < 1 or snap["status"] != "draft":
        raise ValueError("Invalid draft season/week/version/status")
    players, availability = draft["players"], draft["availability"]
    if not players or len(players) != len(availability):
        raise ValueError("Player and availability counts must match and be nonzero")
    ids = []
    for p in players:
        if set(p) != COLUMNS["players"] or not all(str(p[k]).strip() for k in ("player_id", "player_name", "team", "projection_model")):
            raise ValueError("Invalid player fields")
        if p["position"] not in {"QB", "RB", "WR", "TE"}:
            raise ValueError("Invalid position")
        try:
            points = Decimal(str(p["projected_ppr"]))
        except InvalidOperation as exc:
            raise ValueError("Invalid PPR") from exc
        if not points.is_finite() or points.as_tuple().exponent < -2 or abs(points) >= Decimal("1000000"):
            raise ValueError("PPR incompatible with numeric(8,2)")
        rank = p["projected_position_rank"]
        if type(rank) is not int or rank <= 0:
            raise ValueError("Invalid position rank")
        ids.append(p["player_id"])
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate player IDs")
    available_ids = []
    for a in availability:
        if set(a) != COLUMNS["availability"]:
            raise ValueError("Invalid availability fields")
        if a["availability"] is not None or a["observed_at"] is not None:
            raise ValueError("Unverified availability/observed_at must remain null")
        available_ids.append(a["player_id"])
    if Counter(ids) != Counter(available_ids):
        raise ValueError("Availability/player IDs differ")
    return season, week, version, len(ids)


class Supabase:
    def __init__(self):
        url = os.environ.get("SUPABASE_URL", "").rstrip("/")
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        if not url.startswith("https://") or not key:
            raise ValueError("Set SUPABASE_URL (https) and SUPABASE_SERVICE_ROLE_KEY in environment")
        self.base = url + "/rest/v1/"
        self.key = key

    def request(self, table, method="GET", params=None, payload=None, prefer=None):
        url = self.base + table
        if params:
            url += "?" + urllib.parse.urlencode(params)
        body = None if payload is None else json.dumps(payload, allow_nan=False).encode()
        headers = {"apikey": self.key, "Authorization": "Bearer " + self.key, "Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if prefer:
            headers["Prefer"] = prefer
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                data = response.read()
                return json.loads(data) if data else []
        except urllib.error.HTTPError as exc:
            # Do not print response bodies; they may include sensitive data.
            raise RuntimeError(f"Supabase {table} {method} failed: HTTP {exc.code}") from exc

    def count(self, table, snapshot_id):
        rows = self.request(table, params={"select": "player_id", "snapshot_id": "eq." + snapshot_id, "limit": "1000"})
        return len(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--draft", required=True, type=Path)
    parser.add_argument("--source-commit", help="Git commit SHA of approved source CSV (optional)")
    parser.add_argument("--apply", action="store_true", help="Explicitly create a draft and insert rows")
    args = parser.parse_args()
    draft = json.loads(args.draft.read_text(encoding="utf-8"))
    season, week, version, count = validate(draft)
    print(f"Validated season={season} week={week} version={version}: {count} players and {count} availability rows")
    if not args.apply:
        print("DRY RUN: no network request or database changes. Pass --apply to import.")
        return

    db = Supabase()
    existing = db.request("pro_projection_snapshots", params={
        "select": "id,status", "season": f"eq.{season}", "week": f"eq.{week}", "version": f"eq.{version}",
    })
    if existing:
        raise RuntimeError("Snapshot version already exists; refusing to overwrite or append")

    snapshot = {"season": season, "week": week, "version": version, "status": "draft"}
    if args.source_commit:
        if not (len(args.source_commit) == 40 and all(c in "0123456789abcdefABCDEF" for c in args.source_commit)):
            raise ValueError("--source-commit must be a 40-character Git commit SHA")
        snapshot["source_commit"] = args.source_commit.lower()

    created = db.request("pro_projection_snapshots", "POST", payload=snapshot, prefer="return=representation")
    if len(created) != 1:
        raise RuntimeError("Unexpected snapshot creation response; inspect database manually")
    snapshot_id = created[0]["id"]
    print(f"Created DRAFT snapshot {snapshot_id}")
    try:
        for offset in range(0, count, 100):
            batch = [dict(p, snapshot_id=snapshot_id) for p in draft["players"][offset:offset + 100]]
            db.request("pro_projection_players", "POST", payload=batch, prefer="return=minimal")
        for offset in range(0, count, 100):
            batch = [dict(a, snapshot_id=snapshot_id) for a in draft["availability"][offset:offset + 100]]
            db.request("pro_player_availability", "POST", payload=batch, prefer="return=minimal")
        player_count = db.count("pro_projection_players", snapshot_id)
        availability_count = db.count("pro_player_availability", snapshot_id)
        if (player_count, availability_count) != (count, count):
            raise RuntimeError(f"Count mismatch: players={player_count}, availability={availability_count}, expected={count}")
        print(f"Verified DRAFT snapshot {snapshot_id}: {player_count} players, {availability_count} availability")
        print("Snapshot remains DRAFT; no approval or live-site change.")
    except Exception:
        print(f"IMPORT INCOMPLETE for snapshot {snapshot_id}. No automatic deletion/retry; inspect database.")
        raise


if __name__ == "__main__":
    main()
