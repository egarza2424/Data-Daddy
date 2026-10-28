"""Fail-closed J2 input validation before weekly production projection build."""
from pathlib import Path
import sys
import numpy as np
import pandas as pd

ROOT=Path('projection-model')
snap=pd.read_csv(ROOT/'current-live-model-snapshot.csv')
weeks=pd.to_numeric(snap['snapshot_week'],errors='coerce').dropna().unique()
if len(weeks)!=1: raise SystemExit('J2 GATE BLOCKED: ambiguous snapshot week')
week=int(weeks[0])
path=ROOT/'validation'/f'2026-week{week}-rb-j2-experimental.csv'
if not path.exists(): raise SystemExit(f'J2 GATE BLOCKED: missing {path}')
j2=pd.read_csv(path)
required={'player_name','team','snapshot_week','j2_source','j2_projection_status','j2_projected_ppr'}
if required-set(j2): raise SystemExit('J2 GATE BLOCKED: missing required columns')
if set(pd.to_numeric(j2['snapshot_week'],errors='coerce').dropna().astype(int))!={week}:
    raise SystemExit('J2 GATE BLOCKED: stale/mismatched week')
if j2.duplicated(['player_name','team']).any():
    raise SystemExit('J2 GATE BLOCKED: duplicate RB identities')
eligible=j2['j2_projection_status'].eq('experimental_2026_features')
vals=pd.to_numeric(j2.loc[eligible,'j2_projected_ppr'],errors='coerce')
if eligible.sum()<1 or not np.isfinite(vals).all() or (vals<0).any():
    raise SystemExit('J2 GATE BLOCKED: invalid eligible projections')
if not j2.loc[eligible,'j2_source'].eq('2026_pregame').all():
    raise SystemExit('J2 GATE BLOCKED: unverified fallback in eligible set')
excluded=j2.loc[~eligible]
if excluded['j2_projected_ppr'].notna().any():
    raise SystemExit('J2 GATE BLOCKED: excluded player has J2 PPR')
jacobs=snap.loc[(snap['player_name']=='Josh Jacobs') & (snap['team']=='GB')]
strong=j2.loc[(j2['player_name']=='Pierre Strong Jr.') & (j2['team']=='GB')]
if not jacobs.empty and not jacobs['roster_status'].astype(str).str.lower().eq('inactive').all():
    if len(strong)!=1 or strong.iloc[0]['j2_projection_status']!='role_review_required_starter_return':
        raise SystemExit('J2 GATE BLOCKED: returning-starter Strong guard absent')
print(f'J2 INPUT GATE PASS: week={week}, eligible={eligible.sum()}, excluded={len(excluded)}')
print('EXCLUDED RB REVIEW:')
if excluded.empty:
    print('None')
else:
    print(excluded[['player_name','team','j2_source','j2_projection_status']].sort_values(['j2_projection_status','team','player_name']).to_string(index=False))
print('NOTE: This validates input integrity, NOT comprehensive injury/role accuracy.')
