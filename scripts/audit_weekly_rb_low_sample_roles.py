"""Read-only evidence audit for every low-sample J2 role exclusion."""
from pathlib import Path
import pandas as pd

ROOT=Path('projection-model')
snap=pd.read_csv(ROOT/'current-live-model-snapshot.csv',dtype={'player_id':str})
week=int(pd.to_numeric(snap['snapshot_week'],errors='coerce').dropna().iloc[0])
features=pd.read_csv(ROOT/'validation/2026-live-rb-j2-features-audit.csv',dtype={'j2_stats_player_id':str})
excluded=features.loc[pd.to_numeric(features['rb_season_games'],errors='coerce').lt(3) & features['j2_match_status'].isin(['matched','matched_name_only'])].copy()
if excluded.empty:
    print('No low-sample RB exclusions to audit')
    raise SystemExit(0)
weekly=pd.read_csv('https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_2026.csv',dtype={'player_id':str})
weekly['week']=pd.to_numeric(weekly['week'],errors='coerce')
weekly['season']=pd.to_numeric(weekly['season'],errors='coerce')
weekly=weekly.loc[weekly['season'].eq(2026)&weekly['week'].lt(week)&weekly['position'].eq('RB')].copy()
if 'season_type' in weekly: weekly=weekly.loc[weekly['season_type'].eq('REG')]
for col in ['carries','targets','receptions']:
    weekly[col]=pd.to_numeric(weekly[col],errors='coerce').fillna(0)
rows=[]
for player in excluded.itertuples(index=False):
    f=features.loc[(features['player_name']==player.player_name)&(features['team']==player.team)]
    if len(f)!=1: raise ValueError(f'Ambiguous identity: {player.player_name}')
    pid=f.iloc[0]['j2_stats_player_id']
    hist=weekly.loc[weekly['player_id'].eq(pid)].sort_values('week') if pd.notna(pid) else weekly.iloc[:0]
    latest=hist.tail(1)
    team=snap.loc[snap['team'].eq(player.team)&snap['position'].eq('RB'),['player_name','roster_status','injury_status','position_rank']]
    peers='; '.join(f"{r.player_name} [{r.roster_status}; injury={r.injury_status}; AI rank={r.position_rank}]" for r in team.itertuples(index=False) if r.player_name!=player.player_name)
    last_week=int(latest.iloc[0]['week']) if len(latest) else None
    carries=float(latest.iloc[0]['carries']) if len(latest) else None
    targets=float(latest.iloc[0]['targets']) if len(latest) else None
    rows.append(dict(player_name=player.player_name,team=player.team,recorded_games=len(hist),last_recorded_week=last_week,last_carries=carries,last_targets=targets,last_opportunities=(carries+targets if carries is not None else None),last_3_carries=round(float(hist.tail(3)['carries'].sum()),1),last_3_targets=round(float(hist.tail(3)['targets'].sum()),1),current_roster_status=(snap.loc[(snap['player_name'].eq(player.player_name))&(snap['team'].eq(player.team)),'roster_status'].iloc[0]),current_injury_status=(snap.loc[(snap['player_name'].eq(player.player_name))&(snap['team'].eq(player.team)),'injury_status'].iloc[0]),teammate_snapshot=peers,review='MANUAL_ROLE_REVIEW_REQUIRED'))
out=pd.DataFrame(rows).sort_values(['team','player_name'])
path=ROOT/'validation'/f'2026-week{week}-rb-low-sample-role-review.csv'
path.parent.mkdir(parents=True,exist_ok=True)
out.to_csv(path,index=False)
print(out[['player_name','team','recorded_games','last_recorded_week','last_carries','last_targets','last_3_carries','last_3_targets','current_roster_status','current_injury_status']].to_string(index=False))
print(f'Saved {path}; review only; no automatic reinstatements or projection changes.')
