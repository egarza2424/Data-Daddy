"""Audit-only, pregame RB J2 feature export. Does NOT change production.

Run from repository root:
 python scripts/build_live_rb_j2_features.py
Requires pandas and numpy; downloads nflverse 2026 weekly stats and PBP.
"""
from pathlib import Path
import re
import tempfile
from urllib.request import urlretrieve

import pandas as pd
from build_historical_ppr_dataset import prepare_stats, load_red_zone_pbp, attach_red_zone_stats

SEASON = 2026
SNAPSHOT = Path('projection-model/current-live-model-snapshot.csv')
OUTPUT = Path('projection-model/validation/2026-live-rb-j2-features-audit.csv')
WEEKLY_URL = 'https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_2026.csv'
PBP_URL = 'https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_2026.csv.gz'
STATS = ['carries', 'targets', 'receptions', 'rushing_yards', 'receiving_yards']


def normalized_name(value):
    return re.sub(r'[^a-z0-9]', '', re.sub(r'\s+(jr\.?|sr\.?|ii|iii|iv)$', '', str(value).lower().strip()))


def main():
    snapshot = pd.read_csv(SNAPSHOT, dtype={'player_id': str})
    weeks = pd.to_numeric(snapshot['snapshot_week'], errors='coerce').dropna().unique()
    if len(weeks) != 1 or int(weeks[0]) < 2:
        raise ValueError('Live snapshot must have one valid target week')
    target_week = int(weeks[0])
    live = snapshot.loc[snapshot['position'].eq('RB')].copy()
    if live.empty or live['player_id'].duplicated().any():
        raise ValueError('Missing RB rows or duplicate live player IDs')
    weekly = pd.read_csv(WEEKLY_URL, dtype={'player_id': str})
    required = {'season', 'week', 'player_id', 'position', *STATS}
    if required - set(weekly.columns):
        raise ValueError(f'Weekly stats missing columns: {sorted(required - set(weekly.columns))}')
    weekly = prepare_stats(weekly)
    history = weekly.loc[(weekly['season'] == SEASON) & (weekly['week'] < target_week) & weekly['position'].eq('RB')].copy()
    if history.empty:
        raise ValueError('No pregame 2026 RB statistics available')
    if history.duplicated(['player_id', 'week']).any():
        raise ValueError('Duplicate player-week stats; refusing ambiguous totals')
    with tempfile.TemporaryDirectory() as temp:
        pbp_path = Path(temp) / 'play_by_play_2026.csv.gz'
        urlretrieve(PBP_URL, pbp_path)
        redzone = load_red_zone_pbp(pbp_path, SEASON)
    history = attach_red_zone_stats(history, redzone)
    history['normalized_name'] = history['player_display_name'].map(normalized_name)
    history['normalized_team'] = history['team'].astype(str).str.upper().replace({'LA': 'LAR', 'JAC': 'JAX', 'WSH': 'WAS'})
    live['normalized_name'] = live['player_name'].map(normalized_name)
    live['normalized_team'] = live['team'].astype(str).str.upper().replace({'LA': 'LAR', 'JAC': 'JAX', 'WSH': 'WAS'})
    # The live site uses numeric IDs while nflverse uses GSIS IDs. Resolve only
    # unique name+team matches; flag all ambiguous/unmatched identities.
    lookup = history.groupby(['normalized_name', 'normalized_team'])['player_id'].unique()
    name_lookup = history.groupby('normalized_name')['player_id'].unique()
    records = []
    for row in live.itertuples(index=False):
        key = (row.normalized_name, row.normalized_team)
        candidates = lookup.get(key, [])
        match_status = 'matched'
        if len(candidates) == 0:
            candidates = name_lookup.get(row.normalized_name, [])
            match_status = 'matched_name_only'
        record = {'snapshot_week': target_week, 'player_id': row.player_id,
                  'player_name': row.player_name, 'team': row.team,
                  'implied_team_total': row.implied_team_total,
                  'j2_stats_player_id': '', 'j2_match_status': 'unmatched'}
        if len(candidates) == 1:
            player_history = history.loc[history['player_id'].eq(candidates[0])].sort_values('week')
            recent = player_history.tail(3)
            record['j2_stats_player_id'] = str(candidates[0])
            record['j2_match_status'] = match_status
            record['rb_prior_games'] = len(recent)
            record['rb_season_games'] = len(player_history)
            for col, out in [('carries', 'carries'), ('targets', 'targets'),
                             ('receptions', 'receptions'), ('rushing_yards', 'rush_yards'),
                             ('receiving_yards', 'receiving_yards')]:
                record[f'rb_{out}_pg'] = float(recent[col].mean())
                record[f'rb_season_{out}'] = float(player_history[col].sum())
            record['rb_redzone_carries_pg'] = float(recent['red_zone_carries'].mean())
            record['rb_redzone_targets_pg'] = float(recent['red_zone_targets'].mean())
        elif len(candidates) > 1:
            record['j2_match_status'] = 'ambiguous'
        records.append(record)
    output = pd.DataFrame(records)
    if output.duplicated('player_id').any():
        raise ValueError('Duplicate player IDs in audit output')
    resolved = output.loc[output['j2_stats_player_id'].ne('')]
    if resolved['j2_stats_player_id'].duplicated().any():
        raise ValueError('Same nflverse player matched to multiple live RBs')
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(OUTPUT, index=False)
    print(f'Wrote {OUTPUT}; target week={target_week}; stats cutoff week<{target_week}')
    print(output['j2_match_status'].value_counts().to_string())
    print('Unmatched and ambiguous players:')
    print(output.loc[~output['j2_match_status'].isin(['matched', 'matched_name_only']), ['player_name', 'team', 'j2_match_status']].to_string(index=False))
    print('AUDIT ONLY: Model F and production outputs unchanged.')


if __name__ == '__main__':
    main()
