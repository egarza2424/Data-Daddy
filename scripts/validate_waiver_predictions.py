#!/usr/bin/env python3
"""Audit frozen waiver Top 10 snapshots against recorded weekly PPR.

Conservative policy: a snapshot must be explicitly verified as pregame before
its results are counted in predictive accuracy summaries. Missing games are
never assumed to be zero-point performances.
"""
import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_SNAPSHOTS = Path('data/waiver_snapshots')
DEFAULT_STATS = Path('nfl-stats.json')
DEFAULT_OUTPUT = Path('data/waiver_validation')


def parse_time(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace('Z', '+00:00')).astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def collect_player_games(stats):
    """Return {(player_id, season, week): points} from supported structures.

    Reject ambiguous player IDs or duplicate/conflicting game records.
    """
    records = stats.get('recent_player_performance')
    if records is None:
        raise ValueError('nfl-stats.json has no recent_player_performance section')
    if isinstance(records, dict):
        iterable = [(key, value) for key, value in records.items()]
    elif isinstance(records, list):
        iterable = [(None, value) for value in records]
    else:
        raise ValueError('recent_player_performance must be a dict or list')

    games = {}
    conflicts = set()
    for dictionary_key, player in iterable:
        if not isinstance(player, dict):
            continue
        player_id = player.get('player_id') or player.get('id') or dictionary_key
        if not player_id:
            continue
        for game in player.get('games', []):
            if not isinstance(game, dict):
                continue
            try:
                key = (str(player_id), int(game['season']), int(game['week']))
                points = game.get('ppr_points')
                if points is None:
                    continue
                points = float(points)
            except (KeyError, ValueError, TypeError):
                continue
            if key in games and games[key] != points:
                conflicts.add(key)
            else:
                games[key] = points
    for key in conflicts:
        games.pop(key, None)
    return games, conflicts


def audit_snapshot(path, games, conflicts, pregame_approved):
    snapshot = json.loads(path.read_text(encoding='utf-8'))
    season, week = int(snapshot['season']), int(snapshot['target_week'])
    generated = parse_time(snapshot.get('last_updated'))
    # No schedule/kickoff feed is supplied here. Timing cannot be independently verified.
    timing = 'manually_verified_pregame' if path.name in pregame_approved else 'pregame_unverified'
    if generated is None:
        timing = 'missing_snapshot_timestamp'
    recommendations = snapshot.get('provisional_top_10', [])
    rows = []
    for index, candidate in enumerate(recommendations, start=1):
        player_id = str(candidate.get('player_id') or '')
        key = (player_id, season, week)
        if key in conflicts:
            result_status, actual = 'conflicting_stat_records', None
        elif key in games:
            result_status, actual = 'recorded_game', games[key]
        else:
            result_status, actual = 'missing_game_or_unavailable', None
        signal = (candidate.get('candidate_injury_opportunity_assessment') or {}).get('signal')
        rows.append({
            'snapshot_file': path.name,
            'snapshot_generated_utc': generated.isoformat() if generated else '',
            'season': season, 'target_week': week,
            'pregame_status': timing,
            'rank': candidate.get('provisional_rank', index),
            'original_rank': candidate.get('original_rank', ''),
            'player_id': player_id,
            'name': candidate.get('name', ''),
            'team': candidate.get('team', ''),
            'position': candidate.get('position', ''),
            'waiver_evidence_score': candidate.get('waiver_evidence_score', ''),
            'injury_opportunity_signal': signal or '',
            'result_status': result_status,
            'actual_ppr': actual if actual is not None else '',
            'eligible_for_predictive_accuracy': timing == 'manually_verified_pregame' and result_status == 'recorded_game',
        })
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshots', type=Path, default=DEFAULT_SNAPSHOTS)
    parser.add_argument('--stats', type=Path, default=DEFAULT_STATS)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--approve-pregame', action='append', default=[], metavar='SNAPSHOT_FILENAME',
                        help='Use only after independently verifying all relevant kickoff times and snapshot timestamp')
    args = parser.parse_args()
    if not args.stats.is_file():
        parser.error(f'Missing stats file: {args.stats}')
    if not args.snapshots.is_dir():
        parser.error(f'Missing snapshot folder: {args.snapshots}')
    stats = json.loads(args.stats.read_text(encoding='utf-8'))
    games, conflicts = collect_player_games(stats)
    paths = sorted(args.snapshots.glob('waiver_*_week_*.json'))
    if not paths:
        parser.error(f'No weekly snapshots in {args.snapshots}')
    rows = []
    for path in paths:
        rows.extend(audit_snapshot(path, games, conflicts, set(args.approve_pregame)))
    if not rows:
        parser.error('Snapshots contain no provisional_top_10 recommendations')
    args.output.mkdir(parents=True, exist_ok=True)
    csv_path = args.output / 'waiver_prediction_audit.csv'
    with csv_path.open('w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    eligible = [r for r in rows if r['eligible_for_predictive_accuracy']]
    grouped = defaultdict(list)
    for row in eligible:
        grouped[row['position']].append(float(row['actual_ppr']))
    summary = {
        'snapshot_files': len(paths),
        'recommendation_rows': len(rows),
        'recorded_game_rows': sum(r['result_status'] == 'recorded_game' for r in rows),
        'missing_or_unavailable_rows': sum(r['result_status'] == 'missing_game_or_unavailable' for r in rows),
        'conflicting_stat_records': len(conflicts),
        'predictive_accuracy_eligible_rows': len(eligible),
        'eligible_average_ppr': round(sum(float(r['actual_ppr']) for r in eligible) / len(eligible), 2) if eligible else None,
        'eligible_average_ppr_by_position': {p: round(sum(v) / len(v), 2) for p, v in sorted(grouped.items())},
        'note': 'No unverified snapshots count toward predictive accuracy; absent game records are not zeroes. '
                'PPR is read from nfl-stats.json, not recalculated.',
    }
    summary_path = args.output / 'waiver_validation_summary.json'
    summary_path.write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary, indent=2))
    print(f'Wrote {csv_path} and {summary_path}')


if __name__ == '__main__':
    main()
