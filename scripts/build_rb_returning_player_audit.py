"""Audit historical baselines for live RBs without 2026 games.

Does not alter live projections. Run after build_live_rb_j2_features.py.
"""
from pathlib import Path
import re
import pandas as pd

AUDIT = Path('projection-model/validation/2026-live-rb-j2-features-audit.csv')
OUT = Path('projection-model/validation/2026-rb-returning-player-audit.csv')
URL = 'https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_2025.csv'
COLS = ['carries', 'targets', 'receptions', 'rushing_yards', 'receiving_yards', 'rushing_tds', 'receiving_tds']


def norm(s):
    s = str(s).lower().strip()
    s = re.sub(r'\s+(jr\.?|sr\.?|ii|iii|iv)$', '', s)
    return re.sub(r'[^a-z0-9]', '', s)


def main():
    if not AUDIT.exists():
        raise FileNotFoundError(f'Run live J2 audit first: {AUDIT}')
    audit = pd.read_csv(AUDIT, dtype={'player_id': str})
    missing = audit.loc[audit['j2_match_status'].eq('unmatched')].copy()
    if missing.empty:
        print('No unmatched RBs; nothing to backfill.')
        return
    prior = pd.read_csv(URL, dtype={'player_id': str})
    name_col = next((c for c in ('player_display_name', 'player_name') if c in prior.columns), None)
    if name_col is None or 'position' not in prior.columns or 'week' not in prior.columns:
        raise ValueError('Unexpected 2025 nflverse schema')
    for col in COLS:
        if col not in prior.columns:
            raise ValueError(f'Missing required historical field: {col}')
        prior[col] = pd.to_numeric(prior[col], errors='coerce').fillna(0)
    prior = prior.loc[prior['position'].eq('RB')].copy()
    if 'season_type' in prior.columns:
        prior = prior.loc[prior['season_type'].eq('REG')].copy()
    prior['name_key'] = prior[name_col].map(norm)
    prior['week'] = pd.to_numeric(prior['week'], errors='coerce')
    missing['name_key'] = missing['player_name'].map(norm)
    rows = []
    for row in missing.itertuples(index=False):
        candidates = prior.loc[prior['name_key'].eq(row.name_key)]
        ids = candidates['player_id'].dropna().unique()
        result = {'snapshot_week': row.snapshot_week, 'player_id': row.player_id,
                  'player_name': row.player_name, 'current_team': row.team,
                  'source_season': 2025, 'historical_match_status': 'no_2025_history',
                  'historical_player_id': '', 'historical_games': 0,
                  'availability_status': 'requires_current_verification',
                  'projection_ready': False}
        if len(ids) == 1:
            games = candidates.loc[candidates['player_id'].eq(ids[0])].sort_values('week')
            if games['week'].duplicated().any():
                result['historical_match_status'] = 'duplicate_week_records'
            else:
                result['historical_match_status'] = 'unique_2025_history'
                result['historical_player_id'] = str(ids[0])
                result['historical_games'] = len(games)
                for col in COLS:
                    result[f'prior_{col}_per_game'] = round(float(games[col].mean()), 4)
                    result[f'prior_{col}_total'] = round(float(games[col].sum()), 4)
                result['prior_ppr_per_game'] = round(float((games['rushing_yards']/10 + games['receiving_yards']/10 + games['receptions'] + 6*(games['rushing_tds'] + games['receiving_tds'])).mean()), 4)
        elif len(ids) > 1:
            result['historical_match_status'] = 'ambiguous_2025_identity'
        rows.append(result)
    output = pd.DataFrame(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(OUT, index=False)
    print(f'Wrote {OUT}')
    print(output['historical_match_status'].value_counts().to_string())
    print(output[['player_name','historical_match_status','historical_games','prior_ppr_per_game']].to_string(index=False))
    print('AUDIT ONLY: no production projection, ranking, or availability changes.')


if __name__ == '__main__':
    main()
