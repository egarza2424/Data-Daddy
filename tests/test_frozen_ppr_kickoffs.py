"""Regression tests for kickoff eligibility and immutable PPR audit safety."""
import ast
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import verify_frozen_ppr_kickoffs as verifier

class FreezeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "model-snapshots").mkdir()
        (self.root / "data").mkdir()
        date = "2026-10-24"
        self.meta = self.root / "model-snapshots" / f"{date}-pregame-ppr-projections.json"
        self.csv = self.root / "model-snapshots" / f"{date}-pregame-ppr-projections.csv"
        self.meta.write_text(json.dumps({"snapshot_utc": "2026-10-24T15:00:00+00:00", "week": 7, "audit_status": "requires per-game kickoff verification"}))
        self.csv.write_text("player_id,team,position,snapshot_week,projected_ppr,projected_position_rank,position_rank\n1,NE,QB,7,20,1,1\n")
        (self.root / "data" / "nfl_schedule_2026.json").write_text(json.dumps({"games": [{"week": "7", "gameday": "2026-10-25", "gametime": "13:00", "home_team": "NE", "away_team": "NYJ"}]}))
        self.cwd = Path.cwd()

    def run_verify(self):
        import os
        os.chdir(self.root)
        try:
            verifier.verify("2026-10-24")
        finally:
            os.chdir(self.cwd)

    def test_eligible_snapshot_is_verified(self):
        self.run_verify()
        self.assertEqual(json.loads(self.meta.read_text())["audit_status"], "kickoff_verified")

    def test_postkickoff_snapshot_is_rejected(self):
        obj = json.loads(self.meta.read_text())
        obj["snapshot_utc"] = "2026-10-25T18:00:00+00:00"
        self.meta.write_text(json.dumps(obj))
        with self.assertRaisesRegex(RuntimeError, "postkickoff"):
            self.run_verify()
        self.assertNotEqual(json.loads(self.meta.read_text())["audit_status"], "kickoff_verified")

    def test_unknown_team_is_rejected(self):
        self.csv.write_text(self.csv.read_text().replace(",NE,", ",XXX,"))
        with self.assertRaisesRegex(RuntimeError, "missing teams"):
            self.run_verify()

    def test_missing_kickoff_is_rejected(self):
        path = self.root / "data" / "nfl_schedule_2026.json"
        obj = json.loads(path.read_text())
        obj["games"][0]["gametime"] = ""
        path.write_text(json.dumps(obj))
        with self.assertRaisesRegex(RuntimeError, "missing game date/time"):
            self.run_verify()

if __name__ == "__main__":
    unittest.main()
