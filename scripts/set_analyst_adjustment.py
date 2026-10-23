"""Upsert a week-scoped analyst adjustment from authenticated GitHub Actions.

Run with --season --week --player-id --ai-delta --ppr-delta --reason --source --author.
"""
import argparse
import json
from pathlib import Path

from analyst_adjustments import DEFAULT_CONFIG, load_adjustments, _delta


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--player-id", required=True)
    parser.add_argument("--ai-delta", default="0.00")
    parser.add_argument("--ppr-delta", default="0.00")
    parser.add_argument("--reason", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--author", required=True)
    args = parser.parse_args()
    if not 1 <= args.week <= 22:
        parser.error("week must be between 1 and 22")
    if args.season < 2020:
        parser.error("invalid season")
    player_id = args.player_id.strip()
    if not player_id or not all(x.strip() for x in (args.reason, args.source, args.author)):
        parser.error("player ID, reason, source and author cannot be empty")
    ai = _delta(args.ai_delta, "ai_delta")
    ppr = _delta(args.ppr_delta, "ppr_delta")
    path = Path(DEFAULT_CONFIG)
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data["adjustments"]
    rows[:] = [r for r in rows if not (
        r.get("season") == args.season and r.get("week") == args.week
        and str(r.get("player_id")) == player_id
    )]
    if ai or ppr:
        rows.append({
            "season": args.season, "week": args.week,
            "player_id": player_id,
            "ai_score_delta": str(ai), "projected_ppr_delta": str(ppr),
            "reason": args.reason.strip(), "source": args.source.strip(),
            "author": args.author.strip(),
        })
    # Validate all stored entries, not just the selected week.
    import tempfile
    with tempfile.TemporaryDirectory() as directory:
        test = Path(directory) / "adjustments.json"
        test.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        load_adjustments(test, season=args.season, week=args.week)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Saved week {args.week} analyst adjustment for player {player_id}")


if __name__ == "__main__":
    main()
