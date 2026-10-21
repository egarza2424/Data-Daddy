"""Audit-only Week 7 RB J2 challenger. Does not write production projections.
Run after the two live RB audits. Train on 2025 historical RB player-weeks
with pregame features; never train on 2026 Week 7 results.
"""
from pathlib import Path
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_rb_model_j2 import features, priors, ols

ROOT = Path('projection-model')
LIVE = ROOT / 'validation/2026-live-rb-j2-features-audit.csv'
RETURNING = ROOT / 'validation/2026-rb-returning-player-audit.csv'
TRAIN = ROOT / '2025-historical-ppr-dataset.csv'
SNAPSHOT = ROOT / 'current-live-model-snapshot.csv'
OUT = ROOT / 'validation/2026-week7-rb-j2-experimental.csv'
CORE = ['rb_prior_games','rb_carries_pg','rb_targets_pg','rb_receptions_pg',
        'rb_rush_yards_pg','rb_receiving_yards_pg','rb_redzone_carries_pg',
        'rb_redzone_targets_pg','rb_season_games','rb_season_carries',
        'rb_season_targets','rb_season_receptions','rb_season_rush_yards',
        'rb_season_receiving_yards','implied_team_total']


def main():
    for p in [LIVE, RETURNING, TRAIN, SNAPSHOT]:
        if not p.exists():
            raise FileNotFoundError(f'Missing prerequisite: {p}')
    hist = pd.read_csv(TRAIN)
    hist = hist.loc[hist['position'].eq('RB') & hist['week'].ge(7)].copy()
    if hist.empty or hist[CORE + ['actual_ppr']].isna().any().any():
        raise ValueError('Historical J2 training data missing or incomplete')
    live = pd.read_csv(LIVE, dtype={'player_id':str})
    if live['snapshot_week'].nunique() != 1 or int(live['snapshot_week'].iloc[0]) != 7:
        raise ValueError('Expected frozen Week 7 snapshot; refusing other week')
    if live['player_id'].duplicated().any():
        raise ValueError('Duplicate RB live identities')
    snap = pd.read_csv(SNAPSHOT, dtype={'player_id':str})
    status = snap[['player_id','injury_status','roster_status']].drop_duplicates('player_id')
    live = live.merge(status, on='player_id', how='left', validate='one_to_one')
    prior = pd.read_csv(RETURNING, dtype={'player_id':str})
    prior = prior.loc[prior['historical_match_status'].eq('unique_2025_history')].copy()
    prior = prior.drop_duplicates('player_id')
    live = live.merge(prior, on='player_id', how='left', suffixes=('','_2025'), validate='one_to_one')
    live['j2_source'] = np.where(live['j2_match_status'].isin(['matched','matched_name_only']), '2026_pregame', 'unavailable')
    # A previous-season fallback is a provisional input only, NOT a 2026 workload forecast.
    # Never pretend the player has current-season games or infer red-zone usage from absent data.
    fallback = live['j2_source'].eq('unavailable') & live['historical_match_status'].eq('unique_2025_history')
    live.loc[fallback, 'j2_source'] = '2025_fallback_provisional'
    for c in CORE:
        if c not in live:
            live[c] = np.nan
    for i in live.index[fallback]:
        n = float(live.at[i, 'historical_games'])
        if n <= 0:
            continue
        live.at[i, 'rb_prior_games'] = min(3, n)
        live.at[i, 'rb_season_games'] = n
        for key, label in [('carries','carries'),('targets','targets'),('receptions','receptions'),
                           ('rushing_yards','rush_yards'),('receiving_yards','receiving_yards')]:
            live.at[i, f'rb_{label}_pg'] = live.at[i, f'prior_{key}_per_game']
            live.at[i, f'rb_season_{label}'] = live.at[i, f'prior_{key}_total']
        # Red-zone stats are unavailable in this fallback: mark it unrankable rather than assume zero.
    live['j2_projection_status'] = 'not_projected'
    valid = live['j2_source'].eq('2026_pregame') & live[CORE].notna().all(axis=1)
    if not valid.any():
        raise ValueError('No eligible 2026 RBs with complete J2 features')
    p = priors(hist)
    train_x = features(hist, p, 'J2_RB_role_stability')
    test_x = features(live.loc[valid], p, 'J2_RB_role_stability')
    live['j2_projected_ppr'] = np.nan
    live.loc[valid, 'j2_projected_ppr'] = np.round(ols(train_x, hist['actual_ppr'], test_x), 2)
    live.loc[valid, 'j2_projection_status'] = 'experimental_2026_features'
    # Only rank comparable 2026-data players. Returning players remain visible but not mis-ranked.
    live['j2_rank_2026_data_only'] = live['j2_projected_ppr'].rank(method='min', ascending=False)
    keep = ['player_name','team','snapshot_week','injury_status','roster_status','j2_source',
            'j2_match_status','historical_games','prior_ppr_per_game','j2_projection_status',
            'j2_projected_ppr','j2_rank_2026_data_only']
    OUT.parent.mkdir(parents=True, exist_ok=True)
    live[keep].sort_values('j2_projected_ppr', ascending=False, na_position='last').to_csv(OUT,index=False)
    print(f'Wrote {OUT} | training rows={len(hist)} | projected={valid.sum()} | historical fallback flagged={fallback.sum()}')
    print(live[keep].sort_values('j2_projected_ppr', ascending=False, na_position='last').head(24).to_string(index=False))
    print('WARNING: 2025 fallback players are NOT projected until red-zone/role/availability are validated.')
    print('AUDIT ONLY: Production Model F unchanged.')

if __name__ == '__main__':
    main()
