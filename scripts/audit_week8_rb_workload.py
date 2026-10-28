"""Read-only Week 8 RB workload review. Requires the live J2 feature export.
Uses pregame 2026 weekly statistics; no production files are modified.
"""
from pathlib import Path
import pandas as pd

FEATURES = Path('projection-model/validation/2026-live-rb-j2-features-audit.csv')
SNAPSHOT = Path('projection-model/current-live-model-snapshot.csv')
OUT = Path('projection-model/validation/2026-week8-rb-workload-review.csv')
URL = 'https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_2026.csv'
WATCH = {'Pierre Strong Jr.', 'Josh Jacobs', 'Tony Pollard', 'Emanuel Wilson', 'Braelon Allen'}
COLS = ['carries','targets','receptions','rushing_yards','receiving_yards']

def main():
    features = pd.read_csv(FEATURES, dtype={'player_id':str, 'j2_stats_player_id':str})
    if set(features['snapshot_week'].dropna().astype(int)) != {8}:
        raise ValueError('Expected Week 8 pregame features')
    snap = pd.read_csv(SNAPSHOT, dtype={'player_id':str})
    watch = features.loc[features['player_name'].isin(WATCH)].copy()
    if set(watch['player_name']) != WATCH:
        raise ValueError('Missing targeted RBs: '+str(WATCH-set(watch['player_name'])))
    weekly = pd.read_csv(URL, dtype={'player_id':str})
    weekly['week'] = pd.to_numeric(weekly['week'], errors='coerce')
    weekly['season'] = pd.to_numeric(weekly['season'], errors='coerce')
    weekly = weekly.loc[(weekly['season']==2026) & weekly['week'].between(1,7)].copy()
    if 'season_type' in weekly:
        weekly = weekly.loc[weekly['season_type'].eq('REG')].copy()
    for c in COLS:
        weekly[c] = pd.to_numeric(weekly[c],errors='coerce')
    if weekly.duplicated(['player_id','week']).any():
        raise ValueError('Duplicate weekly player records')
    rows=[]
    for f in watch.itertuples(index=False):
        hist=weekly.loc[weekly['player_id'].eq(f.j2_stats_player_id)].sort_values('week')
        if hist.empty:
            rows.append({'player_name':f.player_name,'team':f.team,'review_flag':'NO_VERIFIED_HISTORY'})
            continue
        recent=hist.tail(3)
        for g in hist.itertuples(index=False):
            row={'player_name':f.player_name,'team':f.team,'week':int(g.week),
                 'is_last_three':int(g.week) in set(recent['week']),
                 'review_flag':'CHECK_STARTER_AVAILABILITY_AND_ROLE'}
            for c in COLS: row[c]=getattr(g,c)
            rows.append(row)
    output=pd.DataFrame(rows).sort_values(['player_name','week'])
    OUT.parent.mkdir(parents=True,exist_ok=True)
    output.to_csv(OUT,index=False)
    print(output.to_string(index=False))
    print('Saved',OUT)
    print('REVIEW ONLY: Starter availability is NOT inferred from workload.')
    print('No rankings, scores, weights, or projections changed.')

if __name__=='__main__':
    main()
