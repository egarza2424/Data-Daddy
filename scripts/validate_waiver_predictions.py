#!/usr/bin/env python3
"""Audit frozen waiver Top 10 snapshots against recorded weekly PPR.

Conservative policy: a snapshot must precede each player's scheduled kickoff
before its results count in predictive accuracy summaries. Missing games are
never assumed to be zero-point performances.
"""
import argparse
import csv
import json
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

DEFAULT_SNAPSHOTS = Path('data/waiver_snapshots')
DEFAULT_STATS = Path('nfl-stats.json')
DEFAULT_OUTPUT = Path('data/waiver_validation')
DEFAULT_SCHEDULE_URL = 'https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv'
TEAM_ALIASES = {'LA': 'LAR', 'JAC': 'JAX', 'WSH': 'WAS', 'OAK': 'LV'}


def parse_time(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace('Z', '+00:00')).astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None



def normalize_team(team):
    value = str(team or '').strip().upper()
    return TEAM_ALIASES.get(value, value)


def load_kickoffs(schedule_url):
    """Map (season, week, team) to unique scheduled UTC kickoff.

    nflverse nfldata games.csv gameday/gametime are US Eastern local time.
    Missing, malformed or ambiguous records remain ineligible.
    """
    kickoffs = {}
    ambiguous = set()
    try:
        with urllib.request.urlopen(schedule_url, timeout=25) as response:
            reader = csv.DictReader(line.decode('utf-8-sig') for line in response)
            required = {'season', 'week', 'game_type', 'gameday', 'gametime', 'home_team', 'away_team'}
            if not required.issubset(set(reader.fieldnames or [])):
                raise ValueError('NFL schedule missing required columns')
            for row in reader:
                if str(row.get('game_type', '')).strip() != 'REG':
                    continue
                try:
                    season = int(row['season'])
                    week = int(row['week'])
                except (ValueError, TypeError):
                    continue
                day, clock = (row.get('gameday') or '').strip(), (row.get('gametime') or '').strip()
                if not day or not clock:
                    continue
                try:
                    kickoff = datetime.fromisoformat(f'{day}T{clock}').replace(
                        tzinfo=ZoneInfo('America/New_York')
                    ).astimezone(timezone.utc)
                except ValueError:
                    continue
                for raw_team in (row.get('home_team'), row.get('away_team')):
                    team = normalize_team(raw_team)
                    if not team:
                        continue
                    key = (season, week, team)
                    if key in kickoffs:
                        ambiguous.add(key)
                    else:
                        kickoffs[key] = kickoff
    except (OSError, ValueError, TimeoutError) as error:
        print(f'NFL kickoff schedule unavailable; timing remains unverified: {error}')
        return {}, set()
    for key in ambiguous:
        kickoffs.pop(key, None)
    return kickoffs, ambiguous


def collect_player_games(stats):
    """Collect weekly PPR from full player history and recent records.

    Reject conflicting records. Missing games are never treated as zero.
    """
    games = {}
    conflicts = set()

    def add_game(player_id, season, week, points):
        if not player_id or points is None:
            return
        try:
            key = (str(player_id), int(season), int(week))
            value = round(float(points), 2)
        except (TypeError, ValueError):
            return

        if key in conflicts:
            return
        if key in games and games[key] != value:
            conflicts.add(key)
            games.pop(key, None)
        else:
            games[key] = value

    def calculate_ppr(row):
        fields = {
            'passing_yards': 1 / 25,
            'passing_tds': 4,
            'interceptions': -2,
            'rushing_yards': 1 / 10,
            'rushing_tds': 6,
            'receptions': 1,
            'receiving_yards': 1 / 10,
            'receiving_tds': 6,
        }
        try:
            return sum(
                float(row.get(field) or 0) * weight
                for field, weight in fields.items()
            )
        except (TypeError, ValueError):
            return None

    full_history = stats.get('players', [])
    if not isinstance(full_history, list):
        raise ValueError('nfl-stats.json players must be a list')

    for row in full_history:
        if not isinstance(row, dict):
            continue
        if row.get('season_type') not in ('REG', ''):
            continue
        if row.get('position') not in ('QB', 'RB', 'WR', 'TE'):
            continue
        add_game(
            row.get('player_id'),
            row.get('season'),
            row.get('week'),
            calculate_ppr(row),
        )

    recent = stats.get('recent_player_performance', {})
    if isinstance(recent, dict):
        iterable = recent.items()
    elif isinstance(recent, list):
        iterable = [(None, player) for player in recent]
    else:
        raise ValueError(
            'recent_player_performance must be a dict or list'
        )

    for dictionary_key, player in iterable:
        if not isinstance(player, dict):
            continue
        player_id = (
            player.get('player_id')
            or player.get('id')
            or dictionary_key
        )
        for game in player.get('games', []):
            if not isinstance(game, dict):
                continue
            add_game(
                player_id,
                game.get('season'),
                game.get('week'),
                game.get('ppr_points'),
            )

    return games, conflicts

def audit_snapshot(path, games, conflicts, kickoffs, ambiguous_kickoffs):
    snapshot = json.loads(path.read_text(encoding='utf-8'))
    season, week = int(snapshot['season']), int(snapshot['target_week'])
    generated = parse_time(snapshot.get('last_updated'))
    recommendations = snapshot.get('provisional_top_10', [])
    rows = []
    for index, candidate in enumerate(recommendations, start=1):
        player_id = str(candidate.get('player_id') or '')
        key = (player_id, season, week)
        kickoff_key = (season, week, normalize_team(candidate.get('team')))
        kickoff = kickoffs.get(kickoff_key)
        if generated is None:
            timing = 'missing_snapshot_timestamp'
        elif kickoff_key in ambiguous_kickoffs:
            timing = 'ambiguous_kickoff'
        elif kickoff is None:
            timing = 'kickoff_unavailable'
        elif generated < kickoff:
            timing = 'verified_pregame'
        else:
            timing = 'post_kickoff'
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
            'scheduled_kickoff_utc': kickoff.isoformat() if kickoff else '',
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
            'eligible_for_predictive_accuracy': timing == 'verified_pregame' and result_status == 'recorded_game',
        })
    return rows

def calculate_rank_correlation(rows):
    """Spearman correlation between predicted rank and actual PPR."""
    if len(rows) < 3:
        return None

    def average_ranks(values):
        order = sorted(range(len(values)), key=lambda i: values[i])
        ranks = [0.0] * len(values)
        index = 0

        while index < len(order):
            end = index
            while (
                end + 1 < len(order)
                and values[order[end + 1]] == values[order[index]]
            ):
                end += 1

            rank = (index + end + 2) / 2.0
            for position in range(index, end + 1):
                ranks[order[position]] = rank
            index = end + 1

        return ranks

    try:
        predicted = [
            float(row['rank'])
            for row in rows
        ]
        actual = [
            -float(row['actual_ppr'])
            for row in rows
        ]
    except (ValueError, TypeError, KeyError):
        return None

    predicted_ranks = average_ranks(predicted)
    actual_ranks = average_ranks(actual)

    predicted_mean = sum(predicted_ranks) / len(rows)
    actual_mean = sum(actual_ranks) / len(rows)

    numerator = sum(
        (p - predicted_mean) * (a - actual_mean)
        for p, a in zip(predicted_ranks, actual_ranks)
    )
    predicted_variance = sum(
        (p - predicted_mean) ** 2 for p in predicted_ranks
    )
    actual_variance = sum(
        (a - actual_mean) ** 2 for a in actual_ranks
    )

    denominator = (predicted_variance * actual_variance) ** 0.5
    if denominator == 0:
        return None

    
    return round(numerator / denominator, 3)


def calculate_overall_rank_correlation(weekly_correlations):
    """Calculate the equal-week average of valid weekly correlations."""
    valid_correlations = [
        correlation
        for correlation in weekly_correlations.values()
        if correlation is not None
    ]

    if not valid_correlations:
        return None

    return round(sum(valid_correlations) / len(valid_correlations), 3)


def main():

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshots', type=Path, default=DEFAULT_SNAPSHOTS)
    parser.add_argument('--stats', type=Path, default=DEFAULT_STATS)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--schedule-url', default=DEFAULT_SCHEDULE_URL,
                        help='NFL schedule CSV URL (defaults to nflverse nfldata)')
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
    kickoffs, ambiguous_kickoffs = load_kickoffs(args.schedule_url)
    rows = []
    for path in paths:
        rows.extend(audit_snapshot(path, games, conflicts, kickoffs, ambiguous_kickoffs))
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

    weekly_groups = defaultdict(list)
    for row in eligible:
        weekly_groups[(row['season'], row['target_week'])].append(row)

    
    weekly_rank_correlations = {
        f'{season}_week_{week:02d}': calculate_rank_correlation(week_rows)
        for (season, week), week_rows in sorted(weekly_groups.items())
    }

    overall_rank_correlation = calculate_overall_rank_correlation(weekly_rank_correlations)

    summary = {

        'snapshot_files': len(paths),
        'recommendation_rows': len(rows),
        'recorded_game_rows': sum(r['result_status'] == 'recorded_game' for r in rows),
        'missing_or_unavailable_rows': sum(r['result_status'] == 'missing_game_or_unavailable' for r in rows),
        'conflicting_stat_records': len(conflicts),
        'verified_pregame_rows': sum(r['pregame_status'] == 'verified_pregame' for r in rows),
        'post_kickoff_rows': sum(r['pregame_status'] == 'post_kickoff' for r in rows),
        'timing_unavailable_rows': sum(r['pregame_status'] in ('missing_snapshot_timestamp', 'ambiguous_kickoff', 'kickoff_unavailable') for r in rows),
        'predictive_accuracy_eligible_rows': len(eligible),
        'eligible_average_ppr': round(sum(float(r['actual_ppr']) for r in eligible) / len(eligible), 2) if eligible else None,
        'eligible_average_ppr_by_position': {p: round(sum(v) / len(v), 2) for p, v in sorted(grouped.items())},
        'eligible_spearman_rank_correlation': overall_rank_correlation,
        'eligible_spearman_by_week': weekly_rank_correlations,
        'note': 'Only player-level verified pregame recommendations count toward predictive accuracy; absent game records are not zeroes. '
                'PPR is calculated from full weekly player stats and cross-checked against recent performance records.',
    }
    summary_path = args.output / 'waiver_validation_summary.json'
    summary_path.write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary, indent=2))
    print(f'Wrote {csv_path} and {summary_path}')


if __name__ == '__main__':
    main()
