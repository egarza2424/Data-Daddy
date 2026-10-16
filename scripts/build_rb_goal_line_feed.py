"""Build pregame-only 2026 RB inside-five evidence from nflverse play-by-play.

No projection or scoring changes. Missing team opportunity is not a zero share.
"""
import argparse
import csv
import gzip
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ALIASES = {'LAR': 'LA', 'JAX': 'JAC', 'WAS': 'WSH'}

def norm(s):
    s = str(s or '').strip().upper()
    return ALIASES.get(s, s)

def build(pbp_path, stats_path, output_path, target_week):
    with open(stats_path, encoding='utf-8') as f:
        stats = json.load(f)
    rows = stats.get('players', [])
    if not isinstance(rows, list):
        raise ValueError('nfl-stats.json players must be a list')
    player = defaultdict(lambda: [0, 0])
    team = defaultdict(lambda: [0, 0])
    opener = gzip.open if str(pbp_path).endswith('.gz') else open
    with opener(pbp_path, 'rt', encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        needed = {'season', 'week', 'season_type', 'posteam', 'yardline_100', 'rush_attempt', 'pass_attempt', 'rusher_player_id', 'receiver_player_id'}
        missing = needed - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f'PBP missing required columns: {sorted(missing)}')
        for play in reader:
            try:
                year = int(float(play['season']))
                week = int(float(play['week']))
                yard = float(play['yardline_100'])
            except (ValueError, TypeError):
                continue
            if year != 2026 or play['season_type'] != 'REG' or not (1 <= week < target_week) or not (0 < yard <= 5):
                continue
            offense = norm(play['posteam'])
            if not offense or offense in {'NAN', 'NONE'}:
                continue
            for index, attempt_col, id_col in ((0, 'rush_attempt', 'rusher_player_id'), (1, 'pass_attempt', 'receiver_player_id')):
                if play[attempt_col] == '1':
                    pid = str(play[id_col] or '').strip()
                    if pid:
                        player[(pid, week)][index] += 1
                        team[(offense, week)][index] += 1
    # Stats JSON contains multiple weekly records per player. Use latest team observed strictly before target week.
    candidates = {}
    for row in rows:
        if str(row.get('position', '')).upper() != 'RB':
            continue
        try:
            season = int(row.get('season', 0))
            week = int(row.get('week', 0))
        except (ValueError, TypeError):
            continue
        if season != 2026 or not 1 <= week < target_week:
            continue
        pid = str(row.get('player_id') or '').strip()
        if not pid:
            continue
        if pid not in candidates or week > candidates[pid][0]:
            candidates[pid] = (week, row)
    output = {}
    window = range(max(1, target_week - 3), target_week)
    for pid, (_, row) in sorted(candidates.items()):
        offense = norm(row.get('team') or row.get('recent_team'))
        if not offense:
            continue
        rush = sum(player[(pid, w)][0] for w in window)
        targets = sum(player[(pid, w)][1] for w in window)
        team_rush = sum(team[(offense, w)][0] for w in window)
        team_targets = sum(team[(offense, w)][1] for w in window)
        output[pid] = {
            'player_name': row.get('player_display_name') or row.get('player_name') or pid,
            'team': offense,
            'inside5_rushes_last3weeks': rush,
            'inside5_targets_last3weeks': targets,
            'team_inside5_rushes_last3weeks': team_rush,
            'team_inside5_targets_last3weeks': team_targets,
            'inside5_rush_share_last3weeks': round(rush / team_rush, 4) if team_rush else None,
            'inside5_target_share_last3weeks': round(targets / team_targets, 4) if team_targets else None,
            'status': 'observed' if team_rush else 'no_team_inside5_rush_opportunities',
        }
    payload = {
        'season': 2026, 'target_week': target_week,
        'source': 'nflverse play_by_play_2026.csv.gz',
        'window': 'previous 3 calendar weeks, excluding target week',
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'players': output,
    }
    Path(output_path).write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')
    print(f'Wrote {len(output)} RB records to {output_path}; target_week={target_week}')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--pbp', required=True)
    parser.add_argument('--stats', default='nfl-stats.json')
    parser.add_argument('--output', default='data/rb_goal_line_2026.json')
    parser.add_argument('--target-week', type=int, required=True)
    args = parser.parse_args()
    if not 2 <= args.target_week <= 19:
        parser.error('--target-week must be 2–19')
    build(args.pbp, args.stats, args.output, args.target_week)
