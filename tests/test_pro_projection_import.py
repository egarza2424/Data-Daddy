#!/usr/bin/env python3
"""Offline regression tests for the Pro draft importer; no Supabase calls."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("pro_importer", ROOT / "scripts/import_pro_projection_draft.py")
importer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(importer)


def sample():
    return {
        "snapshot": {"season": 2026, "week": 8, "version": 1, "status": "draft"},
        "players": [
            {"player_id": "101", "player_name": "Test QB", "position": "QB",
             "team": "LA", "projected_ppr": 17.25,
             "projected_position_rank": 1, "projection_model": "test"},
            {"player_id": "102", "player_name": "Test RB", "position": "RB",
             "team": "GB", "projected_ppr": 12.0,
             "projected_position_rank": 1, "projection_model": "test"},
        ],
        "availability": [
            {"player_id": "101", "injury_status": None, "roster_status": "Active",
             "availability": None, "observed_at": None},
            {"player_id": "102", "injury_status": "Questionable", "roster_status": "Active",
             "availability": None, "observed_at": None},
        ],
    }


class ImporterTests(unittest.TestCase):
    def test_valid_draft(self):
        self.assertEqual(importer.validate(sample()), (2026, 8, 1, 2))

    def test_duplicate_player_id_rejected(self):
        data = sample()
        data["players"][1]["player_id"] = "101"
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            importer.validate(data)

    def test_invalid_week_rejected(self):
        data = sample()
        data["snapshot"]["week"] = 23
        with self.assertRaises(ValueError):
            importer.validate(data)

    def test_invalid_version_rejected(self):
        data = sample()
        data["snapshot"]["version"] = 0
        with self.assertRaises(ValueError):
            importer.validate(data)

    def test_unverified_availability_rejected(self):
        data = sample()
        data["availability"][0]["availability"] = "active"
        with self.assertRaises(ValueError):
            importer.validate(data)

    def test_excess_decimal_precision_rejected(self):
        data = sample()
        data["players"][0]["projected_ppr"] = 17.251
        with self.assertRaises(ValueError):
            importer.validate(data)

    def test_dry_run_never_connects(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "draft.json"
            path.write_text(json.dumps(sample()), encoding="utf-8")
            with patch.object(sys, "argv", ["importer", "--draft", str(path)]), \
                 patch.object(importer, "Supabase", side_effect=AssertionError("unexpected connection")), \
                 contextlib.redirect_stdout(io.StringIO()) as output:
                importer.main()
            self.assertIn("DRY RUN", output.getvalue())

    def test_existing_snapshot_refuses_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "draft.json"
            path.write_text(json.dumps(sample()), encoding="utf-8")
            with patch.object(sys, "argv", ["importer", "--draft", str(path), "--apply"]), \
                 patch.object(importer, "Supabase") as mock_db:
                mock_db.return_value.request.return_value = [{"id": "existing", "status": "draft"}]
                with self.assertRaisesRegex(RuntimeError, "already exists"):
                    importer.main()
                self.assertEqual(mock_db.return_value.request.call_count, 1)

    def test_failure_does_not_auto_delete_or_approve(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "draft.json"
            path.write_text(json.dumps(sample()), encoding="utf-8")
            def request(table, method="GET", params=None, payload=None, prefer=None):
                if table == "pro_projection_snapshots" and method == "GET":
                    return []
                if table == "pro_projection_snapshots" and method == "POST":
                    return [{"id": "test-snapshot"}]
                if table == "pro_projection_players" and method == "POST":
                    raise RuntimeError("simulated database failure")
                self.fail(f"Unexpected request: {table} {method}")
            with patch.object(sys, "argv", ["importer", "--draft", str(path), "--apply"]), \
                 patch.object(importer, "Supabase") as mock_db, \
                 contextlib.redirect_stdout(io.StringIO()) as output:
                mock_db.return_value.request.side_effect = request
                with self.assertRaisesRegex(RuntimeError, "simulated database failure"):
                    importer.main()
                self.assertIn("IMPORT INCOMPLETE", output.getvalue())


if __name__ == "__main__":
    unittest.main()
